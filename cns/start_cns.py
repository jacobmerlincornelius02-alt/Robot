#!/usr/bin/env python3
"""Start the robot CNS (Central Nervous System).

Usage:
    python3 start_cns.py

The CNS will start listening on http://0.0.0.0:5000

Endpoints:
    GET  /health     - Health check
    GET  /state      - Full robot state
    GET  /sensors    - Sensor readings
    POST /command    - Send a command
    POST /stop       - Graceful stop
    POST /emergency  - Emergency stop
    POST /reset      - Reset emergency state
    POST /heartbeat  - Send heartbeat

Example commands:
    curl http://robot.local:5000/state
    curl -X POST http://robot.local:5000/command -H "Content-Type: application/json" -d '{"cmd":"move","direction":"forward","distance_cm":50,"speed":70}'
    curl -X POST http://robot.local:5000/stop
"""

import sys
import os

# Ensure we can import from parent directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cns.server import main

if __name__ == '__main__':
    main()
