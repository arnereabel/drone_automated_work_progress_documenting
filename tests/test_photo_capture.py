"""
Tests for Photo Capture module.
"""

import pytest
import numpy as np
import tempfile
from pathlib import Path

from src.utils.storage import StorageManager
from src.modules.photo_capture import PhotoCapture, PhotoCaptureSimulator
from src.config import PhotoConfig, PhotoAngle


class TestPhotoCapture:
    """Tests for PhotoCapture class."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = StorageManager(tmpdir)
            yield storage
    
    @pytest.fixture
    def photo_config(self):
        """Create test photo config."""
        return PhotoConfig(
            angles=[
                PhotoAngle("front", 0),
                PhotoAngle("left45", -45),
                PhotoAngle("right45", 45),
            ],
            delay_between_shots_sec=0.1,
        )
    
    def test_initialization(self, temp_storage, photo_config):
        """Test PhotoCapture initialization."""
        capture = PhotoCapture(temp_storage, photo_config)
        assert capture is not None
        assert len(capture.config.angles) == 3
    
    def test_single_frame_capture(self, temp_storage, photo_config):
        """Test capturing a single frame."""
        capture = PhotoCapture(temp_storage, photo_config)
        
        # Create test frame
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        result = capture.capture_single_frame(
            frame_source=lambda: frame,
            structure_id="TEST_STRUCT",
            stop_number=1,
            angle_name="test",
        )
        
        assert result.success
        assert Path(result.file_path).exists()
    
    def test_capture_with_none_frame(self, temp_storage, photo_config):
        """Test capturing when frame source returns None."""
        capture = PhotoCapture(temp_storage, photo_config)
        
        result = capture.capture_single_frame(
            frame_source=lambda: None,
            structure_id="TEST_STRUCT",
            stop_number=1,
            angle_name="test",
        )
        
        assert not result.success
        assert result.error_message is not None


class TestPhotoCaptureSimulator:
    """Tests for PhotoCaptureSimulator class."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = StorageManager(tmpdir)
            yield storage
    
    def test_simulated_capture(self, temp_storage):
        """Test simulated multi-angle capture."""
        simulator = PhotoCaptureSimulator(temp_storage)
        
        results = simulator.capture_all_angles(
            frame_source=lambda: None,
            structure_id="SIM_TEST",
            stop_number=1,
        )
        
        assert len(results) == 3  # front, left45, right45
        assert all(r.success for r in results)
        
        # Check files exist
        for result in results:
            assert Path(result.file_path).exists()
    
    def test_placeholder_image_content(self, temp_storage):
        """Test that placeholder images have correct content."""
        import cv2
        
        simulator = PhotoCaptureSimulator(temp_storage)
        
        results = simulator.capture_all_angles(
            frame_source=lambda: None,
            structure_id="CONTENT_TEST",
            stop_number=2,
        )
        
        # Load first image
        img = cv2.imread(results[0].file_path)
        
        assert img is not None
        assert img.shape[0] > 0
        assert img.shape[1] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
