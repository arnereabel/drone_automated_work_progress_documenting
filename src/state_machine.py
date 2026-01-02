"""
State Machine for Drone Photography System.

Orchestrates the mission flow through defined states.
"""

import time
from enum import Enum, auto
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field

from .utils.logger import get_logger, LoggerMixin, LogBlock
from .utils.storage import StorageManager
from .config import ConfigManager, Waypoint
from .modules.flight_navigator import FlightNavigator, NavigationState
from .modules.qr_detector import QRDetector
from .modules.photo_capture import PhotoCapture
from .modules.safety import SafetyModule


class MissionState(Enum):
    """States in the mission state machine."""
    IDLE = auto()
    INITIALIZING = auto()
    TAKEOFF = auto()
    NAVIGATING = auto()
    STOPPING = auto()
    DETECTING = auto()
    PHOTOGRAPHING = auto()
    NAVIGATING_NEXT = auto()
    RETURNING_HOME = auto()
    LANDING = auto()
    COMPLETE = auto()
    EMERGENCY = auto()
    ERROR = auto()


@dataclass
class MissionContext:
    """Context data passed between states."""
    current_stop_number: int = 0
    current_structure_id: str = ""
    photos_captured: int = 0
    waypoints_visited: int = 0
    errors: list = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0


class MissionStateMachine(LoggerMixin):
    """
    State machine orchestrating the drone photography mission.
    
    States flow:
    IDLE -> INITIALIZING -> TAKEOFF -> NAVIGATING -> STOPPING -> 
    DETECTING -> PHOTOGRAPHING -> [repeat NAVIGATING...] -> 
    RETURNING_HOME -> LANDING -> COMPLETE
    
    Emergency path:
    Any state -> EMERGENCY -> LANDING -> ERROR
    
    Usage:
        config = load_config()
        machine = MissionStateMachine(config, tello)
        
        # Run synchronously
        machine.run()
        
        # Or step through manually
        machine.start()
        while not machine.is_complete():
            machine.step()
    """
    
    def __init__(
        self,
        config: ConfigManager,
        tello=None,
        simulate: bool = False,
    ):
        """
        Initialize the mission state machine.
        
        Args:
            config: Loaded ConfigManager instance.
            tello: Optional DJITelloPy Tello instance.
            simulate: If True, use simulators instead of real drone.
        """
        self.config = config
        self.tello = tello
        self.simulate = simulate
        
        self._state = MissionState.IDLE
        self._context = MissionContext()
        self._running = False
        
        # Initialize modules (will be set up in INITIALIZING state)
        self.navigator: Optional[FlightNavigator] = None
        self.qr_detector: Optional[QRDetector] = None
        self.photo_capture: Optional[PhotoCapture] = None
        self.safety: Optional[SafetyModule] = None
        self.storage: Optional[StorageManager] = None
        
        # State handlers mapping
        self._state_handlers: Dict[MissionState, Callable[[], MissionState]] = {
            MissionState.IDLE: self._handle_idle,
            MissionState.INITIALIZING: self._handle_initializing,
            MissionState.TAKEOFF: self._handle_takeoff,
            MissionState.NAVIGATING: self._handle_navigating,
            MissionState.STOPPING: self._handle_stopping,
            MissionState.DETECTING: self._handle_detecting,
            MissionState.PHOTOGRAPHING: self._handle_photographing,
            MissionState.NAVIGATING_NEXT: self._handle_navigating_next,
            MissionState.RETURNING_HOME: self._handle_returning_home,
            MissionState.LANDING: self._handle_landing,
            MissionState.COMPLETE: self._handle_complete,
            MissionState.EMERGENCY: self._handle_emergency,
            MissionState.ERROR: self._handle_error,
        }
        
        self.logger.info("MissionStateMachine initialized")
    
    @property
    def state(self) -> MissionState:
        """Get current state."""
        return self._state
    
    @property
    def context(self) -> MissionContext:
        """Get mission context."""
        return self._context
    
    def start(self) -> None:
        """Start the mission."""
        if self._state != MissionState.IDLE:
            self.logger.warning("Mission already started")
            return
        
        self._running = True
        self._context = MissionContext(start_time=time.time())
        self._transition_to(MissionState.INITIALIZING)
        
        self.logger.info("Mission started")
    
    def stop(self) -> None:
        """Stop the mission (graceful shutdown)."""
        self._running = False
        self.logger.info("Mission stop requested")
    
    def step(self) -> MissionState:
        """
        Execute one step of the state machine.
        
        Returns:
            New state after step execution.
        """
        if not self._running:
            return self._state
        
        # Check for emergency before processing state
        if self._check_emergency():
            self._transition_to(MissionState.EMERGENCY)
            return self._state
        
        # Execute current state handler
        handler = self._state_handlers.get(self._state)
        if handler:
            try:
                next_state = handler()
                if next_state != self._state:
                    self._transition_to(next_state)
            except Exception as e:
                self.logger.error(f"State handler error: {e}")
                self._context.errors.append(str(e))
                self._transition_to(MissionState.ERROR)
        
        return self._state
    
    def run(self) -> MissionContext:
        """
        Run the complete mission synchronously.
        
        Returns:
            MissionContext with results.
        """
        self.start()
        
        while self._running and not self.is_complete():
            self.step()
            time.sleep(0.1)  # Small delay between steps
        
        return self._context
    
    def is_complete(self) -> bool:
        """Check if mission is complete (success or error)."""
        return self._state in (
            MissionState.COMPLETE, 
            MissionState.ERROR,
        )
    
    def trigger_emergency(self) -> None:
        """Manually trigger emergency."""
        self.logger.warning("Manual emergency triggered")
        self._transition_to(MissionState.EMERGENCY)
    
    def _transition_to(self, new_state: MissionState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self.logger.info(f"State: {old_state.name} -> {new_state.name}")
    
    def _check_emergency(self) -> bool:
        """Check if emergency should be triggered."""
        if self.safety is None:
            return False
        return self.safety.is_emergency_triggered()
    
    def _get_frame(self):
        """Get frame from drone or None if not available."""
        if self.tello is not None:
            try:
                return self.tello.get_frame_read().frame
            except Exception:
                pass
        return None
    
    # State handlers
    
    def _handle_idle(self) -> MissionState:
        """Handle IDLE state - waiting to start."""
        return MissionState.IDLE
    
    def _handle_initializing(self) -> MissionState:
        """Handle INITIALIZING state - set up modules."""
        with LogBlock("Initializing modules", self.logger):
            # Storage
            self.storage = StorageManager(
                str(self.config.get_output_directory())
            )
            
            # Navigator
            if self.simulate:
                from .modules.flight_navigator import FlightNavigatorSimulator
                self.navigator = FlightNavigatorSimulator(self.config.mission.flight)
            else:
                self.navigator = FlightNavigator(
                    tello=self.tello,
                    config=self.config.mission.flight,
                )
            
            self.navigator.load_waypoints(self.config.waypoints)
            
            # QR Detector
            try:
                self.qr_detector = QRDetector(
                    fallback_id=self.config.mission.detection.fallback_id
                )
            except ImportError as e:
                self.logger.warning(f"QR detector not available: {e}")
                self.qr_detector = None
            
            # Photo Capture
            self.photo_capture = PhotoCapture(
                storage=self.storage,
                config=self.config.mission.photo,
            )
            
            # Wire up rotation function
            if self.navigator:
                self.photo_capture.set_rotation_function(self.navigator.rotate)
            
            # Safety Module
            try:
                self.safety = SafetyModule(self.config.mission.safety)
                self.safety.set_emergency_callback(self.trigger_emergency)
                
                # Start safety monitoring if we have a frame source
                if self.tello is not None:
                    self.safety.start_monitoring(self._get_frame)
            except ImportError as e:
                self.logger.warning(f"Safety module not available: {e}")
                self.safety = None
        
        return MissionState.TAKEOFF
    
    def _handle_takeoff(self) -> MissionState:
        """Handle TAKEOFF state."""
        with LogBlock("Takeoff", self.logger):
            if self.navigator.takeoff():
                return MissionState.NAVIGATING
            else:
                self._context.errors.append("Takeoff failed")
                return MissionState.ERROR
    
    def _handle_navigating(self) -> MissionState:
        """Handle NAVIGATING state - moving to waypoint."""
        result = self.navigator.navigate_to_next()
        
        if result.success:
            self._context.current_stop_number += 1
            self._context.waypoints_visited += 1
            return MissionState.STOPPING
        else:
            self._context.errors.append(f"Navigation failed: {result.error_message}")
            return MissionState.ERROR
    
    def _handle_stopping(self) -> MissionState:
        """Handle STOPPING state - stabilizing at waypoint."""
        # Wait for hover to stabilize
        time.sleep(self.config.mission.flight.hover_stability_delay_sec)
        return MissionState.DETECTING
    
    def _handle_detecting(self) -> MissionState:
        """Handle DETECTING state - detecting QR code."""
        if self.qr_detector is None:
            # No QR detector, use unknown ID
            self._context.current_structure_id = "UNKNOWN"
            return MissionState.PHOTOGRAPHING
        
        # Start detection
        self.qr_detector.start_detection(self._get_frame)
        
        # Wait for detection
        structure_id = self.qr_detector.wait_for_detection(
            timeout_sec=self.config.mission.detection.qr_timeout_sec
        )
        
        self.qr_detector.stop_detection()
        
        self._context.current_structure_id = structure_id
        self.logger.info(f"Detected structure: {structure_id}")
        
        return MissionState.PHOTOGRAPHING
    
    def _handle_photographing(self) -> MissionState:
        """Handle PHOTOGRAPHING state - capturing photos."""
        with LogBlock("Photo capture", self.logger):
            # Determine frame source
            if self.simulate:
                # Use placeholder frame generator
                frame_source = lambda: None
            else:
                frame_source = self._get_frame
            
            # Capture all angles
            results = self.photo_capture.capture_all_angles(
                frame_source=frame_source,
                structure_id=self._context.current_structure_id,
                stop_number=self._context.current_stop_number,
            )
            
            # Count successful captures
            successful = sum(1 for r in results if r.success)
            self._context.photos_captured += successful
            
            self.logger.info(
                f"Captured {successful}/{len(results)} photos at stop "
                f"{self._context.current_stop_number}"
            )
        
        return MissionState.NAVIGATING_NEXT
    
    def _handle_navigating_next(self) -> MissionState:
        """Handle NAVIGATING_NEXT state - decide next action."""
        if self.navigator.has_more_waypoints():
            return MissionState.NAVIGATING
        else:
            # All waypoints visited
            if self.config.return_home:
                return MissionState.RETURNING_HOME
            else:
                return MissionState.LANDING
    
    def _handle_returning_home(self) -> MissionState:
        """Handle RETURNING_HOME state."""
        with LogBlock("Return to home", self.logger):
            if self.navigator.return_home():
                return MissionState.LANDING
            else:
                self.logger.warning("Return home failed, landing anyway")
                return MissionState.LANDING
    
    def _handle_landing(self) -> MissionState:
        """Handle LANDING state."""
        with LogBlock("Landing", self.logger):
            # Stop safety monitoring
            if self.safety:
                self.safety.stop_monitoring()
            
            # Land
            self.navigator.land()
            
            self._context.end_time = time.time()
        
        # Check if we came from error/emergency
        if self._context.errors:
            return MissionState.ERROR
        
        return MissionState.COMPLETE
    
    def _handle_complete(self) -> MissionState:
        """Handle COMPLETE state - mission finished successfully."""
        self._running = False
        
        duration = self._context.end_time - self._context.start_time
        
        self.logger.info("=" * 50)
        self.logger.info("MISSION COMPLETE")
        self.logger.info(f"  Duration: {duration:.1f} seconds")
        self.logger.info(f"  Waypoints visited: {self._context.waypoints_visited}")
        self.logger.info(f"  Photos captured: {self._context.photos_captured}")
        self.logger.info("=" * 50)
        
        return MissionState.COMPLETE
    
    def _handle_emergency(self) -> MissionState:
        """Handle EMERGENCY state - immediate landing."""
        self.logger.warning("EMERGENCY STATE - Initiating emergency landing")
        
        # Stop all modules
        if self.safety:
            self.safety.stop_monitoring()
        if self.qr_detector:
            self.qr_detector.stop_detection()
        
        # Emergency land
        if self.navigator:
            self.navigator.emergency_land()
        
        self._context.errors.append("Emergency landing triggered")
        self._context.end_time = time.time()
        
        return MissionState.ERROR
    
    def _handle_error(self) -> MissionState:
        """Handle ERROR state - mission failed."""
        self._running = False
        
        self.logger.error("=" * 50)
        self.logger.error("MISSION FAILED")
        self.logger.error(f"  Errors: {self._context.errors}")
        self.logger.error("=" * 50)
        
        return MissionState.ERROR
