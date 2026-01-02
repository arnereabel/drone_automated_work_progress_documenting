"""
Photo Capture Module for Drone Photography System.

Handles multi-angle photography at each stopping point.
"""

import time
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass

import cv2
import numpy as np

from ..utils.logger import get_logger, LoggerMixin
from ..utils.storage import StorageManager
from ..config import PhotoConfig, PhotoAngle


@dataclass
class CaptureResult:
    """Result of a single photo capture."""
    angle_name: str
    file_path: str
    success: bool
    error_message: Optional[str] = None


class PhotoCapture(LoggerMixin):
    """
    Multi-angle photo capture at waypoints.
    
    Captures photos at configured angles (front, left 45°, right 45°)
    and saves them with organized naming.
    
    Usage:
        capture = PhotoCapture(storage_manager, photo_config)
        
        # Set rotation function from flight controller
        capture.set_rotation_function(drone.rotate_clockwise)
        
        # Capture all angles at a stop
        results = capture.capture_all_angles(
            frame_source=drone.get_frame,
            structure_id="STRUCTURE_A1",
            stop_number=1
        )
    """
    
    def __init__(
        self,
        storage: StorageManager,
        config: Optional[PhotoConfig] = None,
    ):
        """
        Initialize photo capture module.
        
        Args:
            storage: StorageManager instance for saving photos.
            config: PhotoConfig with angle definitions.
        """
        self.storage = storage
        self.config = config or PhotoConfig()
        
        self._rotation_func: Optional[Callable[[int], None]] = None
        self._delay_between_shots = self.config.delay_between_shots_sec
        
        self.logger.info(
            f"PhotoCapture initialized with {len(self.config.angles)} angles"
        )
    
    def set_rotation_function(
        self, 
        rotate_func: Callable[[int], None]
    ) -> None:
        """
        Set the rotation function from flight controller.
        
        Args:
            rotate_func: Function that takes degrees and rotates drone.
                         Positive = clockwise, negative = counter-clockwise.
        """
        self._rotation_func = rotate_func
        self.logger.debug("Rotation function set")
    
    def capture_all_angles(
        self,
        frame_source: Callable[[], np.ndarray],
        structure_id: str,
        stop_number: int,
    ) -> List[CaptureResult]:
        """
        Capture photos at all configured angles.
        
        Process:
        1. For each angle in config:
           a. Rotate to angle (if not front)
           b. Wait for stability
           c. Capture frame
           d. Save photo
        2. Return to original heading
        
        Args:
            frame_source: Callable returning current video frame.
            structure_id: Structure ID from QR detection.
            stop_number: Current waypoint number.
            
        Returns:
            List of CaptureResult for each angle.
        """
        results: List[CaptureResult] = []
        current_rotation = 0  # Track cumulative rotation
        
        self.logger.info(
            f"Starting multi-angle capture for {structure_id} at stop {stop_number}"
        )
        
        for angle in self.config.angles:
            try:
                result = self._capture_single_angle(
                    frame_source=frame_source,
                    structure_id=structure_id,
                    stop_number=stop_number,
                    angle=angle,
                    current_rotation=current_rotation,
                )
                results.append(result)
                
                # Update rotation tracking
                if result.success:
                    current_rotation = angle.rotation
                    
            except Exception as e:
                self.logger.error(f"Error capturing angle {angle.name}: {e}")
                results.append(CaptureResult(
                    angle_name=angle.name,
                    file_path="",
                    success=False,
                    error_message=str(e),
                ))
        
        # Return to original heading
        if current_rotation != 0:
            self._rotate(-current_rotation)
        
        successful = sum(1 for r in results if r.success)
        self.logger.info(
            f"Capture complete: {successful}/{len(results)} photos successful"
        )
        
        return results
    
    def capture_single_frame(
        self,
        frame_source: Callable[[], np.ndarray],
        structure_id: str,
        stop_number: int,
        angle_name: str = "capture",
    ) -> CaptureResult:
        """
        Capture a single frame without rotation.
        
        Args:
            frame_source: Callable returning current video frame.
            structure_id: Structure ID from QR detection.
            stop_number: Current waypoint number.
            angle_name: Name for this capture.
            
        Returns:
            CaptureResult with capture details.
        """
        try:
            frame = frame_source()
            if frame is None:
                return CaptureResult(
                    angle_name=angle_name,
                    file_path="",
                    success=False,
                    error_message="No frame available",
                )
            
            # Save frame
            path = self.storage.save_frame(
                frame=frame,
                structure_id=structure_id,
                stop_number=stop_number,
                angle_name=angle_name,
            )
            
            return CaptureResult(
                angle_name=angle_name,
                file_path=str(path),
                success=True,
            )
            
        except Exception as e:
            return CaptureResult(
                angle_name=angle_name,
                file_path="",
                success=False,
                error_message=str(e),
            )
    
    def _capture_single_angle(
        self,
        frame_source: Callable[[], np.ndarray],
        structure_id: str,
        stop_number: int,
        angle: PhotoAngle,
        current_rotation: int,
    ) -> CaptureResult:
        """
        Capture photo at a single angle.
        
        Args:
            frame_source: Callable returning current frame.
            structure_id: Structure ID.
            stop_number: Stop number.
            angle: PhotoAngle definition.
            current_rotation: Current rotation from original heading.
        """
        # Calculate rotation needed
        rotation_needed = angle.rotation - current_rotation
        
        # Rotate if needed
        if rotation_needed != 0:
            self._rotate(rotation_needed)
            
            # Wait for stability after rotation
            time.sleep(self._delay_between_shots)
        
        # Capture frame
        frame = frame_source()
        if frame is None:
            return CaptureResult(
                angle_name=angle.name,
                file_path="",
                success=False,
                error_message="No frame available",
            )
        
        # Save photo
        path = self.storage.save_frame(
            frame=frame,
            structure_id=structure_id,
            stop_number=stop_number,
            angle_name=angle.name,
        )
        
        self.logger.debug(f"Captured {angle.name} at {path}")
        
        return CaptureResult(
            angle_name=angle.name,
            file_path=str(path),
            success=True,
        )
    
    def _rotate(self, degrees: int) -> None:
        """
        Rotate the drone by specified degrees.
        
        Args:
            degrees: Rotation in degrees. Positive = clockwise.
        """
        if self._rotation_func is None:
            self.logger.warning(
                f"Rotation function not set, skipping {degrees}° rotation"
            )
            return
        
        self.logger.debug(f"Rotating {degrees}°")
        
        # Split into multiple calls if needed (Tello max is usually 360)
        if degrees > 0:
            self._rotation_func(degrees)
        else:
            # Negative rotation = counter-clockwise
            # Tello uses rotate_counter_clockwise for negative
            self._rotation_func(degrees)


class PhotoCaptureSimulator(PhotoCapture):
    """
    Simulated photo capture for testing without a drone.
    
    Generates placeholder images instead of capturing from drone.
    """
    
    def __init__(self, storage: StorageManager, config: Optional[PhotoConfig] = None):
        super().__init__(storage, config)
        self._capture_count = 0
    
    def capture_all_angles(
        self,
        frame_source: Callable[[], np.ndarray],
        structure_id: str,
        stop_number: int,
    ) -> List[CaptureResult]:
        """Simulate capture without actual rotation."""
        results: List[CaptureResult] = []
        
        self.logger.info(f"[SIMULATED] Capturing for {structure_id} at stop {stop_number}")
        
        for angle in self.config.angles:
            # Create a placeholder image
            frame = self._create_placeholder_image(
                structure_id, stop_number, angle.name
            )
            
            # Save it
            path = self.storage.save_frame(
                frame=frame,
                structure_id=structure_id,
                stop_number=stop_number,
                angle_name=angle.name,
            )
            
            results.append(CaptureResult(
                angle_name=angle.name,
                file_path=str(path),
                success=True,
            ))
            
            self._capture_count += 1
            time.sleep(0.5)  # Simulate capture time
        
        return results
    
    def _create_placeholder_image(
        self,
        structure_id: str,
        stop_number: int,
        angle_name: str,
    ) -> np.ndarray:
        """Create a placeholder image with text."""
        # Create blank image
        img = np.zeros((720, 960, 3), dtype=np.uint8)
        img[:] = (50, 50, 50)  # Dark gray background
        
        # Add text
        text_lines = [
            f"Structure: {structure_id}",
            f"Stop: {stop_number}",
            f"Angle: {angle_name}",
            f"[SIMULATED CAPTURE]",
        ]
        
        y_offset = 200
        for line in text_lines:
            cv2.putText(
                img, line, (100, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2
            )
            y_offset += 80
        
        return img
