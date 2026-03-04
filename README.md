# Robot

This project investigates using an LLM to control a simple robot, with a 'central nervous system' (CNS) for real-time motor/sensor control and a 'higher brain function' via LLM.

Current hardware uses a Raspberry Pi, a MotorShield (https://github.com/sbcshop/MotorShield), and a TF-Luna Lidar (https://thepihut.com/products/tf-luna-lidar-ranging-sensor). The code runs on the latest Raspberry Pi OS and is custom for this setup.

![Robot](robot-image.png)

## Getting Started

1. **Install dependencies**
   - Ensure Python 3 and pip are installed.
   - Install required packages:
     ```bash
     pip install -r requirements.txt
     ```

2. **Start the CNS system**
   - Run the main CNS module:
     ```bash
     python3 cns/main.py
     ```

3. **Interact via REST API**
   - The CNS exposes a REST API for movement commands and sensor queries.
   - Example (using `curl`):
     ```bash
     curl -X POST http://<robot-ip>:5000/move -d '{"command": "forward", "duration": 15}' -H "Content-Type: application/json"
     ```

## Using an LLM to Control the Robot

- The LLM can generate natural language instructions (e.g., "head forward for 15 seconds, rotate right 90 degrees, and continue forward for 15 seconds") and send them to the CNS REST API.
- Integrate with your LLM by having it format commands as JSON and POST to the CNS API endpoint.
- The CNS will handle obstacle avoidance using LiDAR and manage command execution, interruption, and resumption.

## Example LLM Integration

1. **LLM generates instruction:**
   - "Move forward for 10 seconds, then turn left 90 degrees."
2. **LLM sends API request:**
   ```python
   import requests
   payload = {"command": "forward", "duration": 10}
   requests.post("http://<robot-ip>:5000/move", json=payload)
   ```
3. **CNS executes and manages safety automatically.**
