"""
Tests for QR Detector module.
"""

import pytest
import numpy as np
import cv2


class TestQRDetector:
    """Tests for QRDetector class."""
    
    def test_import(self):
        """Test that QRDetector can be imported."""
        from src.modules.qr_detector import QRDetector
        assert QRDetector is not None
    
    def test_initialization(self):
        """Test QRDetector initialization."""
        from src.modules.qr_detector import QRDetector
        
        detector = QRDetector(fallback_id="TEST_UNKNOWN")
        assert detector.fallback_id == "TEST_UNKNOWN"
    
    def test_detect_from_empty_frame(self):
        """Test detection on frame without QR code."""
        from src.modules.qr_detector import QRDetector
        
        detector = QRDetector()
        
        # Create blank frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        result = detector.detect_from_frame(frame)
        assert result is None
    
    def test_detect_from_none_frame(self):
        """Test detection on None frame."""
        from src.modules.qr_detector import QRDetector
        
        detector = QRDetector()
        result = detector.detect_from_frame(None)
        assert result is None
    
    def test_visualization_output(self):
        """Test that visualization returns correct tuple."""
        from src.modules.qr_detector import QRDetector
        
        detector = QRDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        data, viz_frame = detector.detect_with_visualization(frame)
        
        assert data is None
        assert viz_frame is not None
        assert viz_frame.shape == frame.shape


class TestQRDetectorWithSampleQR:
    """Tests using generated QR code samples."""
    
    @pytest.fixture
    def sample_qr_frame(self):
        """Generate a frame with a QR code."""
        try:
            import qrcode
            
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data("STRUCTURE_TEST_001")
            qr.make(fit=True)
            
            qr_image = qr.make_image(fill_color="black", back_color="white")
            qr_array = np.array(qr_image.convert("RGB"))
            
            # Place QR in center of larger frame
            frame = np.ones((480, 640, 3), dtype=np.uint8) * 255
            qr_h, qr_w = qr_array.shape[:2]
            
            y_offset = (480 - qr_h) // 2
            x_offset = (640 - qr_w) // 2
            
            frame[y_offset:y_offset+qr_h, x_offset:x_offset+qr_w] = qr_array
            
            return frame
            
        except ImportError:
            pytest.skip("qrcode library not installed")
    
    def test_detect_qr_code(self, sample_qr_frame):
        """Test detection of QR code in frame."""
        from src.modules.qr_detector import QRDetector
        
        detector = QRDetector()
        result = detector.detect_from_frame(sample_qr_frame)
        
        assert result == "STRUCTURE_TEST_001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
