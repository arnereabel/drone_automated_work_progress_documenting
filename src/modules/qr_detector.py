"""
QR Code Detection Module for Drone Photography System.

Detects and decodes QR codes from the video stream to identify
steel structures at stopping points.
"""

import time
from typing import Optional, Tuple, Callable
from threading import Thread, Event

import cv2
import numpy as np

try:
    from pyzbar import pyzbar
    from pyzbar.pyzbar import ZBarSymbol
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False

from ..utils.logger import get_logger, LoggerMixin


class QRDetector(LoggerMixin):
    """
    Detects QR codes from video frames.
    
    Features:
    - Continuous detection from frame source
    - Timeout handling for failed detection
    - Callback support for detection events
    - Thread-safe operation
    
    Usage:
        detector = QRDetector()
        
        # Single frame detection
        qr_data = detector.detect_from_frame(frame)
        
        # Continuous detection with timeout
        detector.start_detection(get_frame_func)
        structure_id = detector.wait_for_detection(timeout_sec=3.0)
        detector.stop_detection()
    """
    
    def __init__(self, fallback_id: str = "UNKNOWN"):
        """
        Initialize QR detector.
        
        Args:
            fallback_id: ID to return when no QR is detected.
        """
        if not PYZBAR_AVAILABLE:
            raise ImportError(
                "pyzbar is required for QR detection. "
                "Install with: pip install pyzbar"
            )
        
        self.fallback_id = fallback_id
        self._detection_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._detected_data: Optional[str] = None
        self._detection_callback: Optional[Callable[[str], None]] = None
        self._frame_source: Optional[Callable[[], np.ndarray]] = None
        
        self.logger.info("QRDetector initialized")
    
    def detect_from_frame(self, frame: np.ndarray) -> Optional[str]:
        """
        Detect and decode QR code from a single frame.
        
        Args:
            frame: OpenCV frame (BGR numpy array).
            
        Returns:
            Decoded QR data string, or None if not found.
        """
        if frame is None:
            return None
        
        # Convert to grayscale for better detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect QR codes
        decoded_objects = pyzbar.decode(gray, symbols=[ZBarSymbol.QRCODE])
        
        if decoded_objects:
            # Return first detected QR
            data = decoded_objects[0].data.decode('utf-8')
            self.logger.debug(f"QR detected: {data}")
            return data
        
        return None
    
    def detect_with_visualization(
        self, 
        frame: np.ndarray
    ) -> Tuple[Optional[str], np.ndarray]:
        """
        Detect QR code and return frame with visualization overlay.
        
        Args:
            frame: OpenCV frame (BGR numpy array).
            
        Returns:
            Tuple of (detected_data, frame_with_overlay).
        """
        if frame is None:
            return None, frame
        
        output_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        decoded_objects = pyzbar.decode(gray, symbols=[ZBarSymbol.QRCODE])
        
        detected_data = None
        
        for obj in decoded_objects:
            # Draw bounding polygon
            points = obj.polygon
            if len(points) == 4:
                pts = np.array(points, dtype=np.int32)
                cv2.polylines(output_frame, [pts], True, (0, 255, 0), 3)
            
            # Draw data text
            data = obj.data.decode('utf-8')
            if detected_data is None:
                detected_data = data
            
            rect = obj.rect
            cv2.putText(
                output_frame,
                data,
                (rect.left, rect.top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
        
        return detected_data, output_frame
    
    def start_detection(
        self,
        frame_source: Callable[[], np.ndarray],
        callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Start continuous QR detection in background thread.
        
        Args:
            frame_source: Callable that returns current frame.
            callback: Optional callback when QR is detected.
        """
        if self._detection_thread is not None and self._detection_thread.is_alive():
            self.logger.warning("Detection already running, stopping first")
            self.stop_detection()
        
        self._frame_source = frame_source
        self._detection_callback = callback
        self._detected_data = None
        self._stop_event.clear()
        
        self._detection_thread = Thread(target=self._detection_loop, daemon=True)
        self._detection_thread.start()
        
        self.logger.info("Started continuous QR detection")
    
    def stop_detection(self) -> None:
        """Stop continuous QR detection."""
        self._stop_event.set()
        
        if self._detection_thread is not None:
            self._detection_thread.join(timeout=2.0)
            self._detection_thread = None
        
        self.logger.info("Stopped QR detection")
    
    def wait_for_detection(self, timeout_sec: float = 3.0) -> str:
        """
        Wait for QR detection or timeout.
        
        Args:
            timeout_sec: Maximum time to wait for detection.
            
        Returns:
            Detected QR data or fallback_id if timeout.
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_sec:
            if self._detected_data is not None:
                result = self._detected_data
                self.logger.info(f"QR detected: {result}")
                return result
            
            if self._stop_event.is_set():
                break
            
            time.sleep(0.1)
        
        self.logger.warning(f"QR detection timeout, using fallback: {self.fallback_id}")
        return self.fallback_id
    
    def get_detected_id(self, timeout_sec: float = 3.0) -> str:
        """
        Alias for wait_for_detection() for API consistency.
        """
        return self.wait_for_detection(timeout_sec)
    
    def is_detecting(self) -> bool:
        """Check if detection is currently running."""
        return (
            self._detection_thread is not None 
            and self._detection_thread.is_alive()
        )
    
    def _detection_loop(self) -> None:
        """Background detection loop."""
        while not self._stop_event.is_set():
            try:
                if self._frame_source is None:
                    time.sleep(0.1)
                    continue
                
                frame = self._frame_source()
                if frame is not None:
                    data = self.detect_from_frame(frame)
                    
                    if data is not None:
                        self._detected_data = data
                        
                        if self._detection_callback:
                            self._detection_callback(data)
                        
                        # Continue running to allow multiple detections
                        # Remove break if you want single-shot behavior
                
                time.sleep(0.1)  # ~10 FPS detection rate
                
            except Exception as e:
                self.logger.error(f"Detection loop error: {e}")
                time.sleep(0.5)


# Standalone test function
def test_qr_with_webcam():
    """Test QR detection using webcam."""
    detector = QRDetector()
    cap = cv2.VideoCapture(0)
    
    print("QR Detection Test - Press 'q' to quit")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        data, viz_frame = detector.detect_with_visualization(frame)
        
        if data:
            print(f"Detected: {data}")
        
        cv2.imshow("QR Detection Test", viz_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    test_qr_with_webcam()
