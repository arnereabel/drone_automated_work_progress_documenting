"""
Safety Module for Drone Photography System.

Provides:
1. Obstacle avoidance via vision-based detection
2. Emergency landing via crossed-arms gesture detection
"""

import time
from typing import Optional, Callable, Tuple
from threading import Thread, Event
from enum import Enum
from dataclasses import dataclass

import cv2
import numpy as np

try:
    import mediapipe as mp
    # Check if solutions attribute exists (API compatibility)
    MEDIAPIPE_AVAILABLE = hasattr(mp, 'solutions')
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    mp = None

from ..utils.logger import get_logger, LoggerMixin
from ..config import SafetyConfig


class EmergencyGesture(Enum):
    """Supported emergency gestures."""
    CROSSED_ARMS = "crossed_arms"
    HANDS_UP = "hands_up"


@dataclass
class SafetyStatus:
    """Current safety status."""
    obstacle_detected: bool = False
    emergency_gesture_detected: bool = False
    obstacle_region: Optional[str] = None  # e.g., "center", "left", "right"
    confidence: float = 0.0


class SafetyModule(LoggerMixin):
    """
    Safety monitoring for drone operations.
    
    Features:
    - Obstacle detection via frame analysis
    - Emergency hand gesture detection (crossed arms X)
    - Continuous background monitoring
    - Callback support for emergency events
    
    Usage:
        safety = SafetyModule(config)
        safety.set_emergency_callback(drone.emergency_land)
        safety.start_monitoring(get_frame_func)
        
        # Check status
        if safety.is_obstacle_ahead():
            drone.stop()
        
        if safety.is_emergency_triggered():
            # Already handled by callback
            pass
        
        safety.stop_monitoring()
    """
    
    def __init__(self, config: Optional[SafetyConfig] = None):
        """
        Initialize safety module.
        
        Args:
            config: SafetyConfig with thresholds and settings.
        """
        self.config = config or SafetyConfig()
        
        # Initialize state first (before any potential exceptions)
        self._status = SafetyStatus()
        self._monitoring_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._frame_source: Optional[Callable[[], np.ndarray]] = None
        self._emergency_callback: Optional[Callable[[], None]] = None
        self._emergency_triggered = False
        self._pose = None
        self._mp_pose = None
        self._mp_draw = None
        
        # Initialize MediaPipe Pose for gesture detection
        if MEDIAPIPE_AVAILABLE and mp is not None:
            try:
                self._mp_pose = mp.solutions.pose
                self._pose = self._mp_pose.Pose(
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._mp_draw = mp.solutions.drawing_utils
            except AttributeError:
                # MediaPipe available but solutions not accessible
                self.logger.warning(
                    "MediaPipe installed but pose solutions not available, "
                    "gesture detection disabled"
                )
                self._pose = None
            except Exception as e:
                self.logger.warning(f"MediaPipe initialization failed: {e}")
                self._pose = None
        else:
            self.logger.warning(
                "MediaPipe not available, gesture detection disabled"
            )
        
        self.logger.info("SafetyModule initialized")
    
    def set_emergency_callback(self, callback: Callable[[], None]) -> None:
        """
        Set callback function for emergency events.
        
        Args:
            callback: Function to call when emergency is triggered.
        """
        self._emergency_callback = callback
        self.logger.debug("Emergency callback set")
    
    def start_monitoring(
        self, 
        frame_source: Callable[[], np.ndarray]
    ) -> None:
        """
        Start background safety monitoring.
        
        Args:
            frame_source: Callable returning current video frame.
        """
        if self._monitoring_thread is not None and self._monitoring_thread.is_alive():
            self.logger.warning("Monitoring already running, stopping first")
            self.stop_monitoring()
        
        self._frame_source = frame_source
        self._stop_event.clear()
        self._emergency_triggered = False
        
        self._monitoring_thread = Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        
        self.logger.info("Started safety monitoring")
    
    def stop_monitoring(self) -> None:
        """Stop background safety monitoring."""
        self._stop_event.set()
        
        if self._monitoring_thread is not None:
            self._monitoring_thread.join(timeout=2.0)
            self._monitoring_thread = None
        
        self.logger.info("Stopped safety monitoring")
    
    def is_emergency_triggered(self) -> bool:
        """Check if emergency gesture was detected."""
        return self._emergency_triggered
    
    def is_obstacle_ahead(self) -> bool:
        """Check if obstacle is detected ahead."""
        return self._status.obstacle_detected
    
    def get_status(self) -> SafetyStatus:
        """Get current safety status."""
        return self._status
    
    def check_frame(self, frame: np.ndarray) -> SafetyStatus:
        """
        Perform safety checks on a single frame.
        
        Args:
            frame: OpenCV frame (BGR numpy array).
            
        Returns:
            SafetyStatus with detection results.
        """
        status = SafetyStatus()
        
        if frame is None:
            return status
        
        # Check for obstacles
        if self.config.obstacle_check_enabled:
            obstacle, region = self._detect_obstacle(frame)
            status.obstacle_detected = obstacle
            status.obstacle_region = region
        
        # Check for emergency gesture
        if self._pose is not None:
            gesture_detected, confidence = self._detect_crossed_arms(frame)
            status.emergency_gesture_detected = gesture_detected
            status.confidence = confidence
        
        return status
    
    def check_frame_with_visualization(
        self, 
        frame: np.ndarray
    ) -> Tuple[SafetyStatus, np.ndarray]:
        """
        Check frame and return with visualization overlay.
        
        Args:
            frame: Input frame.
            
        Returns:
            Tuple of (SafetyStatus, frame_with_overlay).
        """
        if frame is None:
            return SafetyStatus(), frame
        
        output_frame = frame.copy()
        status = SafetyStatus()
        
        # Obstacle detection visualization
        if self.config.obstacle_check_enabled:
            obstacle, region = self._detect_obstacle(frame)
            status.obstacle_detected = obstacle
            status.obstacle_region = region
            
            if obstacle:
                # Draw warning overlay
                cv2.putText(
                    output_frame,
                    f"OBSTACLE: {region}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2,
                )
        
        # Gesture detection with visualization
        if self._pose is not None:
            gesture_detected, confidence, landmarks = self._detect_crossed_arms_with_landmarks(frame)
            status.emergency_gesture_detected = gesture_detected
            status.confidence = confidence
            
            # Draw pose landmarks if detected
            if landmarks is not None:
                self._mp_draw.draw_landmarks(
                    output_frame,
                    landmarks,
                    self._mp_pose.POSE_CONNECTIONS,
                )
            
            if gesture_detected:
                cv2.putText(
                    output_frame,
                    f"EMERGENCY GESTURE ({confidence:.2f})",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2,
                )
        
        return status, output_frame
    
    def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        check_interval = self.config.gesture_check_interval_sec
        
        while not self._stop_event.is_set():
            try:
                if self._frame_source is None:
                    time.sleep(check_interval)
                    continue
                
                frame = self._frame_source()
                if frame is not None:
                    self._status = self.check_frame(frame)
                    
                    # Handle emergency gesture
                    if (
                        self._status.emergency_gesture_detected 
                        and self._status.confidence >= self.config.gesture_confidence_threshold
                        and not self._emergency_triggered
                    ):
                        self._trigger_emergency()
                
                time.sleep(check_interval)
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                time.sleep(0.5)
    
    def _trigger_emergency(self) -> None:
        """Handle emergency trigger."""
        self._emergency_triggered = True
        self.logger.warning("EMERGENCY GESTURE DETECTED - Triggering emergency response")
        
        if self._emergency_callback:
            try:
                self._emergency_callback()
            except Exception as e:
                self.logger.error(f"Emergency callback failed: {e}")
    
    def _detect_obstacle(
        self, 
        frame: np.ndarray
    ) -> Tuple[bool, Optional[str]]:
        """
        Simple obstacle detection based on frame analysis.
        
        Uses edge detection to find significant objects in the center region.
        
        Note: This is a basic implementation. The Tello lacks depth sensors,
        so this is just a rough approximation based on visual features.
        
        Args:
            frame: Input frame.
            
        Returns:
            Tuple of (obstacle_detected, region).
        """
        height, width = frame.shape[:2]
        
        # Define center region (where obstacles matter most)
        center_x1 = int(width * 0.3)
        center_x2 = int(width * 0.7)
        center_y1 = int(height * 0.3)
        center_y2 = int(height * 0.7)
        
        center_region = frame[center_y1:center_y2, center_x1:center_x2]
        
        # Convert to grayscale and detect edges
        gray = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        
        # Calculate edge density
        edge_density = np.sum(edges > 0) / edges.size
        
        if edge_density > self.config.obstacle_threshold:
            return True, "center"
        
        return False, None
    
    def _detect_crossed_arms(
        self, 
        frame: np.ndarray
    ) -> Tuple[bool, float]:
        """
        Detect crossed arms (X) gesture.
        
        Args:
            frame: Input frame.
            
        Returns:
            Tuple of (gesture_detected, confidence).
        """
        detected, confidence, _ = self._detect_crossed_arms_with_landmarks(frame)
        return detected, confidence
    
    def _detect_crossed_arms_with_landmarks(
        self, 
        frame: np.ndarray
    ) -> Tuple[bool, float, any]:
        """
        Detect crossed arms with landmark data.
        
        Crossed arms detection logic:
        - Left wrist should be to the right of body center
        - Right wrist should be to the left of body center
        - Both wrists should be roughly at shoulder height
        
        Args:
            frame: Input frame.
            
        Returns:
            Tuple of (gesture_detected, confidence, landmarks).
        """
        if self._pose is None:
            return False, 0.0, None
        
        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb_frame)
        
        if results.pose_landmarks is None:
            return False, 0.0, None
        
        landmarks = results.pose_landmarks.landmark
        
        # Get relevant landmarks
        left_wrist = landmarks[self._mp_pose.PoseLandmark.LEFT_WRIST]
        right_wrist = landmarks[self._mp_pose.PoseLandmark.RIGHT_WRIST]
        left_shoulder = landmarks[self._mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[self._mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_elbow = landmarks[self._mp_pose.PoseLandmark.LEFT_ELBOW]
        right_elbow = landmarks[self._mp_pose.PoseLandmark.RIGHT_ELBOW]
        
        # Check visibility
        min_visibility = 0.5
        if (
            left_wrist.visibility < min_visibility
            or right_wrist.visibility < min_visibility
            or left_shoulder.visibility < min_visibility
            or right_shoulder.visibility < min_visibility
        ):
            return False, 0.0, results.pose_landmarks
        
        # Calculate body center X
        body_center_x = (left_shoulder.x + right_shoulder.x) / 2
        
        # Check if arms are crossed:
        # Left wrist to the right of center, right wrist to the left
        arms_crossed_x = (
            left_wrist.x > body_center_x 
            and right_wrist.x < body_center_x
        )
        
        # Check if wrists are approximately at chest level
        shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
        wrist_y_avg = (left_wrist.y + right_wrist.y) / 2
        
        # Wrists should be below shoulders but not too far down
        wrists_at_chest = (
            wrist_y_avg > shoulder_y 
            and wrist_y_avg < shoulder_y + 0.3
        )
        
        # Check if elbows are raised (arms forming X shape)
        elbows_raised = (
            left_elbow.y < left_wrist.y
            and right_elbow.y < right_wrist.y
        )
        
        # Calculate confidence based on criteria
        confidence = 0.0
        if arms_crossed_x:
            confidence += 0.4
        if wrists_at_chest:
            confidence += 0.3
        if elbows_raised:
            confidence += 0.3
        
        # Adjust by landmark visibility
        avg_visibility = (
            left_wrist.visibility + right_wrist.visibility
            + left_shoulder.visibility + right_shoulder.visibility
        ) / 4
        confidence *= avg_visibility
        
        is_gesture = confidence >= self.config.gesture_confidence_threshold
        
        return is_gesture, confidence, results.pose_landmarks
    
    def __del__(self):
        """Cleanup resources."""
        self.stop_monitoring()
        if self._pose is not None:
            self._pose.close()


# Standalone test function
def test_safety_with_webcam():
    """Test safety detection using webcam."""
    safety = SafetyModule()
    cap = cv2.VideoCapture(0)
    
    print("Safety Detection Test")
    print("- Cross your arms to trigger emergency gesture")
    print("- Press 'q' to quit")
    
    def emergency_callback():
        print("\n🚨 EMERGENCY CALLBACK TRIGGERED! 🚨\n")
    
    safety.set_emergency_callback(emergency_callback)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        status, viz_frame = safety.check_frame_with_visualization(frame)
        
        # Show status
        status_text = f"Obstacle: {status.obstacle_detected} | Gesture: {status.emergency_gesture_detected} ({status.confidence:.2f})"
        cv2.putText(
            viz_frame, status_text, (10, viz_frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1
        )
        
        cv2.imshow("Safety Detection Test", viz_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    test_safety_with_webcam()
