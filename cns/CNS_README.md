# Robot CNS (Central Nervous System)

A two-layer architecture for AI-controlled robotics, separating real-time reflexive control from high-level planning.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HIGHER BRAIN (Copilot)                   │
│  • Planning & navigation                                    │
│  • Learning environment                                     │
│  • Decision making                                          │
│  • Latency: 1-5 seconds                                     │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP REST API
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    CNS (Raspberry Pi)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Safety    │  │  Command    │  │   State Manager     │  │
│  │   System    │◄─┤   Queue     │  │   • Position est.   │  │
│  │  (Priority) │  │             │  │   • Sensor history  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         ▼                ▼                     ▼             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Hardware Abstraction Layer                 ││
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐  ││
│  │  │ Motors  │ │ Arrows  │ │Ultrasonic│ │     IR       │  ││
│  │  │ (1-4)   │ │ (LEDs)  │ │  Sensor  │ │   Sensors    │  ││
│  │  └─────────┘ └─────────┘ └──────────┘ └──────────────┘  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
sudo apt update
sudo apt install python3-gpiozero python3-flask
```

### 2. Start the CNS

```bash
cd ~/MotorShield
python3 start_cns.py
```

The CNS will start listening on `http://0.0.0.0:5000`

### 3. Test the API

From another terminal or computer:

```bash
# Health check
curl http://robot.local:5000/health

# Get robot state
curl http://robot.local:5000/state

# Move forward 30cm at 50% speed
curl -X POST http://robot.local:5000/command \
  -H "Content-Type: application/json" \
  -d '{"cmd":"move","direction":"forward","distance_cm":30,"speed":50}'

# Stop
curl -X POST http://robot.local:5000/stop
```

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/state` | Full robot state (position, sensors, status) |
| GET | `/sensors` | Current sensor readings |
| POST | `/command` | Execute a command |
| POST | `/stop` | Graceful stop |
| POST | `/emergency` | Emergency stop (immediate) |
| POST | `/reset` | Reset emergency state |
| POST | `/heartbeat` | Send heartbeat (prevents watchdog timeout) |

### Commands

#### Move

```bash
curl -X POST http://robot.local:5000/command \
  -H "Content-Type: application/json" \
  -d '{"cmd":"move","direction":"forward","distance_cm":50,"speed":70}'
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `direction` | string | `"forward"` or `"backward"` |
| `distance_cm` | number | Distance in centimeters |
| `speed` | number | Speed percentage (0-100) |

#### Turn

```bash
curl -X POST http://robot.local:5000/command \
  -H "Content-Type: application/json" \
  -d '{"cmd":"turn","direction":"left","degrees":90,"speed":50}'
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `direction` | string | `"left"` or `"right"` |
| `degrees` | number | Degrees to turn |
| `speed` | number | Speed percentage (0-100) |

#### Arrow Control

```bash
# Single arrow
curl -X POST http://robot.local:5000/command \
  -H "Content-Type: application/json" \
  -d '{"cmd":"arrow","id":3,"state":"on"}'

# Pattern (off, forward, backward, left, right, all, hazard)
curl -X POST http://robot.local:5000/command \
  -H "Content-Type: application/json" \
  -d '{"cmd":"arrows","pattern":"forward"}'
```

| Arrow ID | Position |
|----------|----------|
| 1 | Back |
| 2 | Left |
| 3 | Forward |
| 4 | Right |

#### Stop

```bash
# Graceful stop (finishes current movement step)
curl -X POST http://robot.local:5000/stop

# Emergency stop (immediate, clears command queue)
curl -X POST http://robot.local:5000/emergency

# Reset after emergency
curl -X POST http://robot.local:5000/reset
```

### State Response

```json
{
  "timestamp": 1709513400.123,
  "status": "idle",
  "position": {"x": 0.0, "y": 0.0, "heading": 0.0},
  "velocity": {"linear": 0.0, "angular": 0.0},
  "sensors": {
    "ultrasonic": {"distance_cm": 45.2, "triggered": false},
    "ir1": {"detected": false},
    "ir2": {"detected": false}
  },
  "safety": {
    "collision_imminent": false,
    "last_heartbeat": 1709513399.500
  },
  "command_queue": {
    "current": null,
    "pending": 0
  },
  "arrows": {"1": false, "2": false, "3": false, "4": false}
}
```

**Status values:**
- `idle` - Not moving, ready for commands
- `moving` - Currently executing a movement command
- `stopped` - Stopped by safety system (obstacle detected)
- `emergency` - Emergency stop active, call `/reset` to clear

## Safety Features

The CNS has built-in safety behaviors that **cannot be overridden by the brain**:

| Behavior | Trigger | Action |
|----------|---------|--------|
| **Collision Avoidance** | Ultrasonic < 15cm | Stop motors, set status="stopped" |
| **Watchdog** | No heartbeat > 5s | Stop motors, clear queue |
| **Emergency Stop** | `/emergency` called | Immediate stop, clear queue |
| **Speed Limit** | Speed > 100% | Clamp to 100% |

### Heartbeat

The brain must send a heartbeat at least every 5 seconds to prevent watchdog timeout:

```bash
curl -X POST http://robot.local:5000/heartbeat
```

**Note:** Calling `/state` also counts as a heartbeat.

## Configuration

Edit `cns/config.py` to change settings:

```python
# Safety thresholds
COLLISION_DISTANCE_CM = 15  # Stop if ultrasonic reads less than this
WATCHDOG_TIMEOUT_S = 5.0    # Stop if no heartbeat for this long

# Motor limits
MAX_SPEED = 100  # Maximum speed percentage

# Sensor polling
SAFETY_LOOP_HZ = 50  # Safety system runs at 50Hz
```

## File Structure

```
MotorShield/
├── PiMotor.py              # Hardware library (gpiozero-based)
├── start_cns.py            # Entry point - run this!
├── cns/
│   ├── __init__.py
│   ├── server.py           # Flask HTTP server
│   ├── safety.py           # Safety system thread
│   ├── commands.py         # Command executor
│   ├── state.py            # State manager
│   └── config.py           # Configuration
├── examples/
│   └── brain_example.py    # Example brain interaction
└── CNS_README.md           # This file
```

## Example: Copilot as Brain

Here's how Copilot would control the robot:

```python
import requests

CNS_URL = "http://robot.local:5000"

# 1. Check state
state = requests.get(f"{CNS_URL}/state").json()
print(f"Status: {state['status']}")
print(f"Distance ahead: {state['sensors']['ultrasonic']['distance_cm']}cm")

# 2. Move forward if safe
if not state['safety']['collision_imminent']:
    requests.post(f"{CNS_URL}/command", json={
        "cmd": "move",
        "direction": "forward", 
        "distance_cm": 50,
        "speed": 70
    })

# 3. Check state again
state = requests.get(f"{CNS_URL}/state").json()
if state['status'] == 'stopped':
    print("Obstacle detected! Turning...")
    requests.post(f"{CNS_URL}/command", json={
        "cmd": "turn",
        "direction": "left",
        "degrees": 90
    })
```

## Running as a Service

To start CNS automatically on boot:

```bash
sudo nano /etc/systemd/system/robot-cns.service
```

Add:

```ini
[Unit]
Description=Robot CNS
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/MotorShield/start_cns.py
WorkingDirectory=/home/pi/MotorShield
User=pi
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl enable robot-cns
sudo systemctl start robot-cns
```

## Troubleshooting

### "Address already in use"
```bash
# Find and kill existing process
sudo lsof -i :5000
kill <PID>
```

### "GPIO pin in use"
Restart the Pi or ensure no other Python scripts are running.

### Watchdog keeps stopping motors
Ensure your brain sends heartbeats every few seconds:
```python
import threading
import time
import requests

def heartbeat_loop():
    while True:
        requests.post("http://robot.local:5000/heartbeat")
        time.sleep(2)

threading.Thread(target=heartbeat_loop, daemon=True).start()
```
