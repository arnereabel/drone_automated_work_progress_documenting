# Getting Started - Resume Work

Quick reference for resuming work on this project.

## 1. Open Terminal in Project Directory

```bash
cd c:\Users\arne_r\drone_photo_taking
```

## 2. Activate Virtual Environment

```bash
# Windows
venv\Scripts\activate

# You should see (venv) in your prompt
```

## 3. Verify Setup

```bash
# Check Python is using venv
where python
# Should show: C:\Users\arne_r\drone_photo_taking\venv\Scripts\python.exe

# Run tests to verify everything works
python -m pytest tests/ -v
```

## 4. Common Commands

### Run in Simulation Mode
```bash
python src/main.py
```

### Run with Real Drone
```bash
# First connect to Tello WiFi network
python src/main.py --live
```

### Test Individual Components
```bash
# Test drone connection
python src/main.py --test connection

# Test QR detection with webcam
python src/main.py --test qr

# Test gesture detection with webcam
python src/main.py --test safety
```

---

## Next Tasks (from PROGRESS.md)

1. [ ] Connect to Tello drone (`--test connection`)
2. [ ] Print QR codes for test structures
3. [ ] Test QR detection with webcam
4. [ ] Test crossed-arms gesture
5. [ ] Single waypoint test flight (2m)
6. [ ] Full 3-waypoint MVP test

---

## Useful Files

| File | Purpose |
|------|---------|
| `PROGRESS.md` | Track what's done and next steps |
| `README.md` | Full documentation |
| `config/waypoints_mvp.yaml` | Edit waypoints here |
| `config/mission_default.yaml` | Edit flight/photo settings |

## Deactivate When Done

```bash
deactivate
```
