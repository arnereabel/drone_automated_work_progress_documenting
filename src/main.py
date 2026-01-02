"""
Main Entry Point for Drone Photography System.

Run a photography mission or test individual components.
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, ConfigManager
from src.utils.logger import setup_logger, get_logger
from src.state_machine import MissionStateMachine, MissionState


def run_mission(
    mission_config: str = "config/mission_default.yaml",
    waypoints_config: str = "config/waypoints_mvp.yaml",
    simulate: bool = False,
) -> int:
    """
    Run a complete photography mission.
    
    Args:
        mission_config: Path to mission configuration YAML.
        waypoints_config: Path to waypoints configuration YAML.
        simulate: If True, run in simulation mode without drone.
        
    Returns:
        Exit code (0 = success, 1 = error).
    """
    # Load configuration
    config = load_config(
        mission_path=mission_config,
        waypoints_path=waypoints_config,
        base_path=str(PROJECT_ROOT),
    )
    
    # Set up logging
    setup_logger(
        level=config.mission.logging.level,
        log_file=str(config.get_log_file_path()),
        console=config.mission.logging.console,
    )
    
    logger = get_logger()
    logger.info("=" * 60)
    logger.info("DRONE PHOTOGRAPHY SYSTEM")
    logger.info("=" * 60)
    logger.info(f"Mode: {'SIMULATION' if simulate else 'LIVE'}")
    logger.info(f"Waypoints: {len(config.waypoints)}")
    logger.info(f"Photo angles: {len(config.mission.photo.angles)}")
    logger.info("=" * 60)
    
    # Connect to drone (if not simulating)
    tello = None
    if not simulate:
        try:
            from djitellopy import Tello
            
            logger.info("Connecting to Tello drone...")
            tello = Tello()
            tello.connect()
            
            # Log battery level
            battery = tello.get_battery()
            logger.info(f"Connected! Battery: {battery}%")
            
            if battery < 20:
                logger.warning("Battery low! Consider charging before mission.")
            
            # Start video stream
            tello.streamon()
            logger.info("Video stream started")
            
        except ImportError:
            logger.error("djitellopy not installed. Install with: pip install djitellopy")
            logger.info("Switching to simulation mode...")
            simulate = True
        except Exception as e:
            logger.error(f"Failed to connect to drone: {e}")
            logger.info("Switching to simulation mode...")
            simulate = True
    
    # Create and run state machine
    machine = MissionStateMachine(
        config=config,
        tello=tello,
        simulate=simulate,
    )
    
    try:
        context = machine.run()
        
        # Cleanup
        if tello is not None:
            try:
                tello.streamoff()
                tello.end()
            except Exception:
                pass
        
        # Return code based on result
        if machine.state == MissionState.COMPLETE:
            logger.info("Mission completed successfully!")
            return 0
        else:
            logger.error("Mission failed!")
            return 1
            
    except KeyboardInterrupt:
        logger.warning("Mission interrupted by user")
        machine.stop()
        
        # Emergency land
        if tello is not None:
            try:
                tello.land()
                tello.streamoff()
                tello.end()
            except Exception:
                pass
        
        return 1


def test_connection() -> int:
    """Test drone connection and basic functions."""
    print("Testing Tello connection...")
    
    try:
        from djitellopy import Tello
        
        tello = Tello()
        tello.connect()
        
        print(f"✓ Connected!")
        print(f"  Battery: {tello.get_battery()}%")
        print(f"  Temperature: {tello.get_temperature()}°C")
        print(f"  Flight time: {tello.get_flight_time()}s")
        
        # Test video stream
        print("\nTesting video stream...")
        tello.streamon()
        import time
        time.sleep(2)
        
        frame = tello.get_frame_read().frame
        if frame is not None:
            print(f"✓ Video stream working! Frame shape: {frame.shape}")
        else:
            print("✗ No frame received")
        
        tello.streamoff()
        tello.end()
        
        print("\n✓ All tests passed!")
        return 0
        
    except ImportError:
        print("✗ djitellopy not installed. Install with: pip install djitellopy")
        return 1
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return 1


def test_qr() -> int:
    """Test QR detection with webcam."""
    print("Testing QR detection with webcam...")
    print("Press 'q' to quit")
    
    try:
        from src.modules.qr_detector import test_qr_with_webcam
        test_qr_with_webcam()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def test_safety() -> int:
    """Test safety/gesture detection with webcam."""
    print("Testing safety module with webcam...")
    print("Cross your arms to trigger emergency gesture")
    print("Press 'q' to quit")
    
    try:
        from src.modules.safety import test_safety_with_webcam
        test_safety_with_webcam()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def main():
    """Main entry point with CLI."""
    parser = argparse.ArgumentParser(
        description="Drone Photography System for Steel Structure Documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Run mission in simulation mode
  python main.py --live              # Run mission with real drone
  python main.py --test connection   # Test drone connection
  python main.py --test qr           # Test QR detection with webcam
  python main.py --test safety       # Test gesture detection with webcam
        """,
    )
    
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run with real drone (default is simulation)",
    )
    
    parser.add_argument(
        "--mission-config",
        default="config/mission_default.yaml",
        help="Path to mission configuration file",
    )
    
    parser.add_argument(
        "--waypoints-config",
        default="config/waypoints_mvp.yaml",
        help="Path to waypoints configuration file",
    )
    
    parser.add_argument(
        "--test",
        choices=["connection", "qr", "safety"],
        help="Run a specific test instead of mission",
    )
    
    args = parser.parse_args()
    
    # Handle test modes
    if args.test:
        if args.test == "connection":
            return test_connection()
        elif args.test == "qr":
            return test_qr()
        elif args.test == "safety":
            return test_safety()
    
    # Run mission
    return run_mission(
        mission_config=args.mission_config,
        waypoints_config=args.waypoints_config,
        simulate=not args.live,
    )


if __name__ == "__main__":
    sys.exit(main())
