#!/usr/bin/env python3
"""State manager for the robot CNS."""

import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
from collections import deque


@dataclass
class SensorReading:
    """A single sensor reading with timestamp."""
    value: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class Position:
    """Estimated robot position."""
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0  # degrees, 0 = forward


@dataclass
class Velocity:
    """Current velocity."""
    linear: float = 0.0   # cm/s
    angular: float = 0.0  # degrees/s


class StateManager:
    """Manages robot state and sensor history."""
    
    STATUS_IDLE = "idle"
    STATUS_MOVING = "moving"
    STATUS_STOPPED = "stopped"
    STATUS_EMERGENCY = "emergency"
    
    def __init__(self, history_size: int = 100):
        self._lock = threading.RLock()
        self._status = self.STATUS_IDLE
        self._position = Position()
        self._velocity = Velocity()
        
        # Sensor readings
        self._ultrasonic_cm: Optional[float] = None
        self._ir1_detected: bool = False
        self._ir2_detected: bool = False
        
        # Sensor history (for brain to analyze)
        self._ultrasonic_history: deque = deque(maxlen=history_size)
        
        # Safety state
        self._collision_imminent: bool = False
        self._last_heartbeat: float = time.time()
        
        # Command state
        self._current_command: Optional[Dict] = None
        self._pending_commands: int = 0
        
        # Arrows state
        self._arrows: Dict[int, bool] = {1: False, 2: False, 3: False, 4: False}
    
    def update_ultrasonic(self, distance_cm: float) -> None:
        """Update ultrasonic sensor reading."""
        with self._lock:
            self._ultrasonic_cm = distance_cm
            self._ultrasonic_history.append(
                SensorReading(value=distance_cm)
            )
    
    def update_ir(self, ir1: bool, ir2: bool) -> None:
        """Update IR sensor readings."""
        with self._lock:
            self._ir1_detected = ir1
            self._ir2_detected = ir2
    
    def set_status(self, status: str) -> None:
        """Set robot status."""
        with self._lock:
            self._status = status
    
    def set_collision_imminent(self, imminent: bool) -> None:
        """Set collision imminent flag."""
        with self._lock:
            self._collision_imminent = imminent
    
    def heartbeat(self) -> None:
        """Record heartbeat from brain."""
        with self._lock:
            self._last_heartbeat = time.time()
    
    def get_last_heartbeat(self) -> float:
        """Get timestamp of last heartbeat."""
        with self._lock:
            return self._last_heartbeat
    
    def set_current_command(self, cmd: Optional[Dict]) -> None:
        """Set currently executing command."""
        with self._lock:
            self._current_command = cmd
    
    def set_pending_commands(self, count: int) -> None:
        """Set pending command count."""
        with self._lock:
            self._pending_commands = count
    
    def set_arrow(self, arrow_id: int, state: bool) -> None:
        """Set arrow state."""
        with self._lock:
            if arrow_id in self._arrows:
                self._arrows[arrow_id] = state
    
    def get_ultrasonic(self) -> Optional[float]:
        """Get current ultrasonic reading."""
        with self._lock:
            return self._ultrasonic_cm
    
    def is_collision_imminent(self) -> bool:
        """Check if collision is imminent."""
        with self._lock:
            return self._collision_imminent
    
    def get_status(self) -> str:
        """Get current status."""
        with self._lock:
            return self._status
    
    def get_state(self) -> Dict[str, Any]:
        """Get full state snapshot for API response."""
        with self._lock:
            return {
                "timestamp": time.time(),
                "status": self._status,
                "position": asdict(self._position),
                "velocity": asdict(self._velocity),
                "sensors": {
                    "ultrasonic": {
                        "distance_cm": self._ultrasonic_cm,
                        "triggered": self._collision_imminent
                    },
                    "ir1": {"detected": self._ir1_detected},
                    "ir2": {"detected": self._ir2_detected}
                },
                "safety": {
                    "collision_imminent": self._collision_imminent,
                    "last_heartbeat": self._last_heartbeat
                },
                "command_queue": {
                    "current": self._current_command,
                    "pending": self._pending_commands
                },
                "arrows": self._arrows.copy()
            }
    
    def get_sensors(self) -> Dict[str, Any]:
        """Get just sensor readings."""
        with self._lock:
            return {
                "timestamp": time.time(),
                "ultrasonic": {
                    "distance_cm": self._ultrasonic_cm,
                    "history": [
                        {"value": r.value, "timestamp": r.timestamp}
                        for r in list(self._ultrasonic_history)[-10:]
                    ]
                },
                "ir1": {"detected": self._ir1_detected},
                "ir2": {"detected": self._ir2_detected}
            }
