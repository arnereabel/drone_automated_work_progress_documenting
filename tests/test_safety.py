"""
Tests for Safety module.
"""

import pytest
import numpy as np


class TestSafetyModule:
    """Tests for SafetyModule class."""
    
    def test_import(self):
        """Test that SafetyModule can be imported."""
        from src.modules.safety import SafetyModule
        assert SafetyModule is not None
    
    def test_initialization(self):
        """Test SafetyModule initialization."""
        from src.modules.safety import SafetyModule
        
        safety = SafetyModule()
        assert not safety.is_emergency_triggered()
        assert not safety.is_obstacle_ahead()
    
    def test_check_empty_frame(self):
        """Test safety check on empty frame."""
        from src.modules.safety import SafetyModule
        
        safety = SafetyModule()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        status = safety.check_frame(frame)
        
        assert not status.obstacle_detected
        assert not status.emergency_gesture_detected
    
    def test_check_none_frame(self):
        """Test safety check on None frame."""
        from src.modules.safety import SafetyModule
        
        safety = SafetyModule()
        status = safety.check_frame(None)
        
        assert not status.obstacle_detected
        assert not status.emergency_gesture_detected
    
    def test_visualization_output(self):
        """Test visualization returns correct format."""
        from src.modules.safety import SafetyModule
        
        safety = SafetyModule()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        status, viz_frame = safety.check_frame_with_visualization(frame)
        
        assert viz_frame is not None
        assert viz_frame.shape == frame.shape
    
    def test_emergency_callback_set(self):
        """Test setting emergency callback."""
        from src.modules.safety import SafetyModule
        
        callback_called = []
        
        def my_callback():
            callback_called.append(True)
        
        safety = SafetyModule()
        safety.set_emergency_callback(my_callback)
        
        # Manually trigger for testing
        safety._trigger_emergency()
        
        assert len(callback_called) == 1
        assert safety.is_emergency_triggered()


class TestObstacleDetection:
    """Tests for obstacle detection functionality."""
    
    def test_high_edge_density_detection(self):
        """Test that high edge density triggers obstacle detection."""
        from src.modules.safety import SafetyModule, SafetyConfig
        
        config = SafetyConfig(obstacle_threshold=0.1)  # Lower threshold
        safety = SafetyModule(config)
        
        # Create frame with lots of edges in center
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Add grid pattern in center (high edge density)
        center = frame[150:330, 200:440]
        for i in range(0, center.shape[0], 10):
            center[i:i+2, :] = 255
        for j in range(0, center.shape[1], 10):
            center[:, j:j+2] = 255
        
        status = safety.check_frame(frame)
        
        # Should detect obstacle due to high edge density
        assert status.obstacle_detected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
