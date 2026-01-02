"""
Flight Navigator Module for Drone Photography System.

Handles waypoint-based navigation for the Tello drone.
"""

import time
from typing import List, Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger, LoggerMixin
from ..config import Waypoint, FlightConfig


class NavigationState(Enum):
    """Navigation state."""
    IDLE = "idle"
    NAVIGATING = "navigating"
    AT_WAYPOINT = "at_waypoint"
    RETURNING_HOME = "returning_home"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class NavigationResult:
    """Result of a navigation action."""
    success: bool
    waypoint_name: str
    error_message: Optional[str] = None


class FlightNavigator(LoggerMixin):
    """
    Waypoint-based navigation for Tello drone.
    
    Manages a list of waypoints and provides navigation commands
    to move between them.
    
    Notes on Tello positioning:
    - Tello has no GPS, position is estimated from takeoff point
    - Movement commands are relative (move X cm forward/back/left/right/up/down)
    - Position tracking accumulates error over time
    - For best results, use short distances and visual checkpoints (QR codes)
    
    Usage:
        navigator = FlightNavigator(tello, config)
        navigator.load_waypoints(waypoints)
        
        while navigator.has_more_waypoints():
            result = navigator.navigate_to_next()
            if result.success:
                # At waypoint, do stuff
                pass
            
        navigator.return_home()
    """
    
    def __init__(
        self,
        tello=None,
        config: Optional[FlightConfig] = None,
    ):
        """
        Initialize flight navigator.
        
        Args:
            tello: DJITelloPy Tello instance (can be set later).
            config: FlightConfig with speed and height settings.
        """
        self.tello = tello
        self.config = config or FlightConfig()
        
        self._waypoints: List[Waypoint] = []
        self._current_waypoint_index = -1
        self._state = NavigationState.IDLE
        
        # Position tracking (relative to takeoff, in cm)
        self._current_position = [0, 0, 0]  # x, y, z
        self._home_position = [0, 0, 0]
        
        # Callbacks
        self._on_waypoint_reached: Optional[Callable[[Waypoint], None]] = None
        
        self.logger.info("FlightNavigator initialized")
    
    def set_tello(self, tello) -> None:
        """
        Set or update the Tello instance.
        
        Args:
            tello: DJITelloPy Tello instance.
        """
        self.tello = tello
        self.logger.debug("Tello instance set")
    
    def load_waypoints(self, waypoints: List[Waypoint]) -> None:
        """
        Load waypoints for the mission.
        
        Args:
            waypoints: List of Waypoint objects.
        """
        self._waypoints = waypoints.copy()
        self._current_waypoint_index = -1
        self._state = NavigationState.IDLE
        
        self.logger.info(f"Loaded {len(waypoints)} waypoints")
        for i, wp in enumerate(waypoints):
            self.logger.debug(f"  [{i+1}] {wp.name}: ({wp.x}, {wp.y}, {wp.z})")
    
    def set_waypoint_callback(
        self, 
        callback: Callable[[Waypoint], None]
    ) -> None:
        """
        Set callback for when waypoint is reached.
        
        Args:
            callback: Function taking Waypoint as argument.
        """
        self._on_waypoint_reached = callback
    
    def takeoff(self) -> bool:
        """
        Perform takeoff sequence.
        
        Returns:
            True if takeoff successful.
        """
        if self.tello is None:
            self.logger.error("Tello not connected")
            return False
        
        try:
            self.logger.info("Taking off...")
            self.tello.takeoff()
            
            # Move to configured height
            target_height = self.config.takeoff_height_cm
            current_height = self.tello.get_height()
            
            if current_height < target_height:
                height_diff = target_height - current_height
                self.logger.debug(f"Adjusting height by +{height_diff}cm")
                self.tello.move_up(height_diff)
            
            # Update position
            self._current_position = [0, 0, target_height]
            self._home_position = [0, 0, 0]
            
            # Wait for stability
            time.sleep(self.config.hover_stability_delay_sec)
            
            self.logger.info(f"Takeoff complete at height {target_height}cm")
            return True
            
        except Exception as e:
            self.logger.error(f"Takeoff failed: {e}")
            return False
    
    def land(self) -> bool:
        """
        Perform landing sequence.
        
        Returns:
            True if landing successful.
        """
        if self.tello is None:
            return False
        
        try:
            self.logger.info("Landing...")
            self.tello.land()
            self._state = NavigationState.COMPLETE
            self.logger.info("Landing complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Landing failed: {e}")
            return False
    
    def emergency_land(self) -> None:
        """Perform emergency landing (motors off)."""
        if self.tello is not None:
            self.logger.warning("EMERGENCY LANDING")
            try:
                self.tello.emergency()
            except Exception:
                try:
                    self.tello.land()
                except Exception:
                    pass
        self._state = NavigationState.ERROR
    
    def navigate_to_next(self) -> NavigationResult:
        """
        Navigate to the next waypoint in the list.
        
        Returns:
            NavigationResult with success status.
        """
        if not self.has_more_waypoints():
            return NavigationResult(
                success=False,
                waypoint_name="",
                error_message="No more waypoints",
            )
        
        self._current_waypoint_index += 1
        waypoint = self._waypoints[self._current_waypoint_index]
        
        self.logger.info(
            f"Navigating to waypoint {self._current_waypoint_index + 1}: {waypoint.name}"
        )
        self._state = NavigationState.NAVIGATING
        
        try:
            success = self._navigate_to_position(waypoint.x, waypoint.y, waypoint.z)
            
            if success:
                self._state = NavigationState.AT_WAYPOINT
                
                # Wait for stability
                time.sleep(self.config.hover_stability_delay_sec)
                
                # Trigger callback
                if self._on_waypoint_reached:
                    self._on_waypoint_reached(waypoint)
                
                self.logger.info(f"Reached waypoint: {waypoint.name}")
                return NavigationResult(success=True, waypoint_name=waypoint.name)
            else:
                self._state = NavigationState.ERROR
                return NavigationResult(
                    success=False,
                    waypoint_name=waypoint.name,
                    error_message="Navigation command failed",
                )
                
        except Exception as e:
            self._state = NavigationState.ERROR
            self.logger.error(f"Navigation error: {e}")
            return NavigationResult(
                success=False,
                waypoint_name=waypoint.name,
                error_message=str(e),
            )
    
    def return_home(self) -> bool:
        """
        Navigate back to home position (takeoff point).
        
        Returns:
            True if return successful.
        """
        self.logger.info("Returning to home position...")
        self._state = NavigationState.RETURNING_HOME
        
        try:
            success = self._navigate_to_position(
                self._home_position[0],
                self._home_position[1],
                self._current_position[2],  # Maintain current height
            )
            
            if success:
                self._state = NavigationState.COMPLETE
                self.logger.info("Returned to home position")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Return home failed: {e}")
            return False
    
    def has_more_waypoints(self) -> bool:
        """Check if there are more waypoints to visit."""
        return self._current_waypoint_index < len(self._waypoints) - 1
    
    def get_current_waypoint_index(self) -> int:
        """Get current waypoint index (0-based)."""
        return self._current_waypoint_index
    
    def get_current_waypoint(self) -> Optional[Waypoint]:
        """Get current waypoint object."""
        if 0 <= self._current_waypoint_index < len(self._waypoints):
            return self._waypoints[self._current_waypoint_index]
        return None
    
    def get_current_position(self) -> Tuple[int, int, int]:
        """
        Get estimated current position.
        
        Returns:
            Tuple of (x, y, z) in cm relative to takeoff point.
        """
        return tuple(self._current_position)
    
    def get_state(self) -> NavigationState:
        """Get current navigation state."""
        return self._state
    
    def get_waypoint_count(self) -> int:
        """Get total number of waypoints."""
        return len(self._waypoints)
    
    def rotate(self, degrees: int) -> bool:
        """
        Rotate the drone.
        
        Args:
            degrees: Rotation in degrees. Positive = clockwise.
            
        Returns:
            True if rotation successful.
        """
        if self.tello is None:
            self.logger.warning("Tello not connected, skipping rotation")
            return False
        
        try:
            if degrees > 0:
                self.tello.rotate_clockwise(degrees)
            else:
                self.tello.rotate_counter_clockwise(abs(degrees))
            return True
        except Exception as e:
            self.logger.error(f"Rotation failed: {e}")
            return False
    
    def _navigate_to_position(
        self, 
        target_x: int, 
        target_y: int, 
        target_z: int
    ) -> bool:
        """
        Navigate to absolute position (relative to takeoff).
        
        Uses relative movements to reach target position.
        
        Args:
            target_x: Target X position (cm).
            target_y: Target Y position (cm).
            target_z: Target Z position (cm).
            
        Returns:
            True if navigation successful.
        """
        if self.tello is None:
            self.logger.error("Tello not connected")
            return False
        
        # Calculate relative movements needed
        dx = target_x - self._current_position[0]
        dy = target_y - self._current_position[1]
        dz = target_z - self._current_position[2]
        
        self.logger.debug(
            f"Moving from {self._current_position} to ({target_x}, {target_y}, {target_z})"
        )
        self.logger.debug(f"Relative movement: dx={dx}, dy={dy}, dz={dz}")
        
        # Set speed
        self.tello.set_speed(self.config.movement_speed)
        
        # Execute movements (Z first for safety, then X/Y)
        try:
            # Height adjustment
            if dz > 0:
                self._move_with_limit(self.tello.move_up, dz, "up")
            elif dz < 0:
                self._move_with_limit(self.tello.move_down, abs(dz), "down")
            
            # Forward/backward (X axis)
            if dx > 0:
                self._move_with_limit(self.tello.move_forward, dx, "forward")
            elif dx < 0:
                self._move_with_limit(self.tello.move_back, abs(dx), "back")
            
            # Left/right (Y axis)
            if dy > 0:
                self._move_with_limit(self.tello.move_right, dy, "right")
            elif dy < 0:
                self._move_with_limit(self.tello.move_left, abs(dy), "left")
            
            # Update position tracking
            self._current_position = [target_x, target_y, target_z]
            
            return True
            
        except Exception as e:
            self.logger.error(f"Movement failed: {e}")
            return False
    
    def _move_with_limit(
        self, 
        move_func: Callable[[int], None], 
        distance: int,
        direction: str
    ) -> None:
        """
        Execute movement, splitting into chunks if needed.
        
        Tello has max movement of 500cm per command.
        
        Args:
            move_func: Tello movement function.
            distance: Distance in cm.
            direction: Direction name for logging.
        """
        MAX_MOVE = 500  # cm
        MIN_MOVE = 20   # cm (Tello minimum)
        
        remaining = distance
        
        while remaining > 0:
            move_distance = min(remaining, MAX_MOVE)
            
            if move_distance < MIN_MOVE:
                # Skip very small movements
                self.logger.debug(f"Skipping small movement: {move_distance}cm {direction}")
                break
            
            self.logger.debug(f"Moving {move_distance}cm {direction}")
            move_func(move_distance)
            remaining -= move_distance
            
            # Small delay between chunked movements
            if remaining > 0:
                time.sleep(0.5)


class FlightNavigatorSimulator(FlightNavigator):
    """
    Simulated flight navigator for testing without a drone.
    
    Logs all movements without executing actual drone commands.
    """
    
    def __init__(self, config: Optional[FlightConfig] = None):
        super().__init__(tello=None, config=config)
        self._simulated = True
        self.logger.info("FlightNavigator running in SIMULATION mode")
    
    def takeoff(self) -> bool:
        """Simulate takeoff."""
        self.logger.info("[SIMULATED] Takeoff")
        target_height = self.config.takeoff_height_cm
        self._current_position = [0, 0, target_height]
        self._home_position = [0, 0, 0]
        time.sleep(1)  # Simulate takeoff time
        return True
    
    def land(self) -> bool:
        """Simulate landing."""
        self.logger.info("[SIMULATED] Landing")
        self._state = NavigationState.COMPLETE
        time.sleep(1)  # Simulate landing time
        return True
    
    def emergency_land(self) -> None:
        """Simulate emergency landing."""
        self.logger.warning("[SIMULATED] EMERGENCY LANDING")
        self._state = NavigationState.ERROR
    
    def rotate(self, degrees: int) -> bool:
        """Simulate rotation."""
        self.logger.info(f"[SIMULATED] Rotating {degrees}°")
        time.sleep(0.5)
        return True
    
    def _navigate_to_position(
        self, 
        target_x: int, 
        target_y: int, 
        target_z: int
    ) -> bool:
        """Simulate navigation."""
        dx = target_x - self._current_position[0]
        dy = target_y - self._current_position[1]
        dz = target_z - self._current_position[2]
        
        self.logger.info(
            f"[SIMULATED] Moving to ({target_x}, {target_y}, {target_z}) "
            f"[delta: {dx}, {dy}, {dz}]"
        )
        
        # Simulate movement time (1 second per 100cm)
        distance = (abs(dx) + abs(dy) + abs(dz))
        sim_time = distance / 100.0
        time.sleep(min(sim_time, 3))  # Cap at 3 seconds
        
        self._current_position = [target_x, target_y, target_z]
        return True
