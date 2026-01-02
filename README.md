# Tello Drone Photography System

Automated drone photography system using DJI Tello for documenting work progress on steel structures in an indoor workshop.

## Features

- **Pre-programmed waypoint navigation** - Define stopping points in YAML config
- **QR code structure detection** - Identify structures automatically via QR codes
- **Multi-angle photography** - Capture front, left 45°, right 45° at each stop
- **Emergency gesture detection** - Cross arms (X) to trigger immediate landing
- **Obstacle avoidance** - Vision-based obstacle detection during flight
- **Organized photo storage** - Photos saved by date/structure_ID/stop

## Quick Start

### 1. Install Dependencies

```bash
cd drone_photo_taking
pip install -r requirements.txt
```

**Note:** On Windows, you may need to install Visual C++ Redistributable for `pyzbar`:
https://github.com/NaturalHistoryMuseum/pyzbar#windows

### 2. Run in Simulation Mode

Test the system without a drone:

```bash
python src/main.py
```

### 3. Run with Real Drone

```bash
# Connect your computer to Tello's WiFi
python src/main.py --live
```

## CLI Usage

```
python src/main.py [OPTIONS]

Options:
  --live                  Run with real drone (default is simulation)
  --mission-config PATH   Path to mission config YAML
  --waypoints-config PATH Path to waypoints config YAML
  --test {connection,qr,safety}
                         Run a specific test instead of mission
```

### Test Commands

```bash
# Test drone connection and battery
python src/main.py --test connection

# Test QR detection with webcam
python src/main.py --test qr

# Test crossed-arms gesture detection with webcam
python src/main.py --test safety
```

## Configuration

### Mission Settings (`config/mission_default.yaml`)

```yaml
flight:
  takeoff_height_cm: 100
  movement_speed: 50
  hover_stability_delay_sec: 2.0

photo:
  angles:
    - name: "front"
      rotation: 0
    - name: "left45"
      rotation: -45
    - name: "right45"
      rotation: 45
  delay_between_shots_sec: 1.0

safety:
  obstacle_check_enabled: true
  gesture_confidence_threshold: 0.7
```

### Waypoints (`config/waypoints_mvp.yaml`)

```yaml
waypoints:
  - name: "Stop 1"
    x: 0      # cm from takeoff
    y: 0
    z: 100    # height

  - name: "Stop 2"
    x: 1000   # 10m forward
    y: 0
    z: 100

  - name: "Stop 3"
    x: 2000   # 20m forward
    y: 0
    z: 100

return_home: true
```

## Photo Storage

Photos are saved in the following structure:

```
photos/
└── 2026-01-03/
    ├── STRUCTURE_A1/
    │   ├── stop1_front.jpg
    │   ├── stop1_left45.jpg
    │   └── stop1_right45.jpg
    ├── STRUCTURE_B2/
    │   └── ...
    └── UNKNOWN_STOP2/      # If QR detection failed
        └── ...
```

## Safety Features

### Emergency Hand Gesture

Cross your arms in an **X shape** in front of the drone camera to trigger immediate landing.

### Obstacle Avoidance

The system uses vision-based detection to pause navigation when obstacles are detected in the center of the frame.

> **Note:** The Tello lacks depth sensors, so obstacle detection is approximate.

## Project Structure

```
drone_photo_taking/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration management
│   ├── state_machine.py     # Mission orchestration
│   ├── modules/
│   │   ├── flight_navigator.py  # Waypoint navigation
│   │   ├── qr_detector.py       # QR code detection
│   │   ├── photo_capture.py     # Multi-angle photography
│   │   └── safety.py            # Emergency + obstacle detection
│   └── utils/
│       ├── logger.py        # Logging utilities
│       └── storage.py       # Photo storage management
├── config/
│   ├── mission_default.yaml
│   └── waypoints_mvp.yaml
├── photos/                  # Output directory
├── logs/                    # Mission logs
└── requirements.txt
```

## Extending the System

### Adding More Waypoints

Edit `config/waypoints_mvp.yaml` to add more stopping points:

```yaml
waypoints:
  - name: "Structure Alpha"
    x: 0
    y: 0
    z: 100
    description: "First beam section"
  # Add more...
```

### Custom Photo Angles

Modify the angles in `config/mission_default.yaml`:

```yaml
photo:
  angles:
    - name: "front"
      rotation: 0
    - name: "left90"
      rotation: -90
    - name: "right90"
      rotation: 90
    - name: "back"
      rotation: 180
```

## Known Limitations

1. **Position drift** - Tello uses visual estimation, accuracy degrades over distance
2. **No GPS** - Indoor only, relies on relative positioning
3. **Battery life** - ~13 minutes flight time per battery
4. **WiFi range** - ~100m max (less with obstacles)

## License

MIT
