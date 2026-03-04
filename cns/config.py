#!/usr/bin/env python3
"""Configuration for the CNS (Central Nervous System)."""

# Server settings
HOST = "0.0.0.0"
PORT = 5000

# Safety thresholds
COLLISION_DISTANCE_CM = 15  # Stop if ultrasonic reads less than this
WATCHDOG_TIMEOUT_S = 5.0    # Stop if no heartbeat for this long

# Motor limits
MAX_SPEED = 100  # Maximum speed percentage
MIN_SPEED = 0    # Minimum speed percentage

# Sensor polling
SAFETY_LOOP_HZ = 50  # Safety system runs at 50Hz
SENSOR_POLL_HZ = 10  # Sensor readings for state at 10Hz

# Timing
DEFAULT_MOVE_TIMEOUT_S = 10.0  # Max time for a single move command

# Arrow patterns (predefined LED patterns)
ARROW_PATTERNS = {
    "off": [],
    "forward": [3],      # af
    "backward": [1],     # ab
    "left": [2],         # al
    "right": [4],        # ar
    "all": [1, 2, 3, 4],
    "hazard": [1, 3],    # front and back
}
