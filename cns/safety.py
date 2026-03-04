#!/usr/bin/env python3
"""Safety system for the robot CNS.

This runs in a dedicated thread at high frequency and can override
any motor commands to ensure robot safety.
"""

import time
import threading
from typing import Callable, Optional

from . import config
from .state import StateManager


class SafetySystem:
    """High-priority safety monitoring system."""
    
    def __init__(
        self,
        state: StateManager,
        stop_motors_callback: Callable[[], None],
        read_ultrasonic_callback: Callable[[], Optional[float]]
    ):
        self._state = state
        self._stop_motors = stop_motors_callback
        self._read_ultrasonic = read_ultrasonic_callback
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._emergency_stop = False
        self._lock = threading.Lock()
    
    def start(self) -> None:
        """Start the safety monitoring thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._safety_loop, daemon=True)
        self._thread.start()
        print("[Safety] System started")
    
    def stop(self) -> None:
        """Stop the safety monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        print("[Safety] System stopped")
    
    def emergency_stop(self) -> None:
        """Trigger emergency stop."""
        with self._lock:
            self._emergency_stop = True
        self._stop_motors()
        self._state.set_status(StateManager.STATUS_EMERGENCY)
        print("[Safety] EMERGENCY STOP triggered")
    
    def reset_emergency(self) -> None:
        """Reset emergency stop state."""
        with self._lock:
            self._emergency_stop = False
        self._state.set_status(StateManager.STATUS_IDLE)
        print("[Safety] Emergency reset")
    
    def is_emergency(self) -> bool:
        """Check if in emergency stop state."""
        with self._lock:
            return self._emergency_stop
    
    def _safety_loop(self) -> None:
        """Main safety loop - runs at high frequency."""
        interval = 1.0 / config.SAFETY_LOOP_HZ
        
        while self._running:
            loop_start = time.time()
            
            try:
                self._check_collision()
                self._check_watchdog()
            except Exception as e:
                print(f"[Safety] Error in safety loop: {e}")
            
            # Maintain loop frequency
            elapsed = time.time() - loop_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _check_collision(self) -> None:
        """Check ultrasonic sensor for imminent collision."""
        try:
            distance = self._read_ultrasonic()
            if distance is not None:
                self._state.update_ultrasonic(distance)
                
                if distance < config.COLLISION_DISTANCE_CM:
                    if not self._state.is_collision_imminent():
                        print(f"[Safety] Collision imminent! Distance: {distance:.1f}cm")
                        self._state.set_collision_imminent(True)
                        
                        # Only stop if currently moving
                        if self._state.get_status() == StateManager.STATUS_MOVING:
                            self._stop_motors()
                            self._state.set_status(StateManager.STATUS_STOPPED)
                else:
                    self._state.set_collision_imminent(False)
        except Exception as e:
            print(f"[Safety] Error reading ultrasonic: {e}")
    
    def _check_watchdog(self) -> None:
        """Check if brain has sent heartbeat recently."""
        last_hb = self._state.get_last_heartbeat()
        elapsed = time.time() - last_hb
        
        if elapsed > config.WATCHDOG_TIMEOUT_S:
            status = self._state.get_status()
            if status == StateManager.STATUS_MOVING:
                print(f"[Safety] Watchdog timeout! No heartbeat for {elapsed:.1f}s")
                self._stop_motors()
                self._state.set_status(StateManager.STATUS_STOPPED)
