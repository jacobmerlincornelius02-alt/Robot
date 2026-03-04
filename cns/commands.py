#!/usr/bin/env python3
"""Command executor for the robot CNS."""

import time
import threading
from queue import Queue, Empty
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

from . import config
from .state import StateManager


@dataclass
class Command:
    """A command to execute."""
    cmd_type: str
    params: Dict[str, Any]
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class CommandExecutor:
    """Executes commands from the brain."""
    
    def __init__(
        self,
        state: StateManager,
        motor_forward: Callable[[int], None],
        motor_backward: Callable[[int], None],
        motor_left: Callable[[int], None],
        motor_right: Callable[[int], None],
        motor_stop: Callable[[], None],
        set_arrow: Callable[[int, bool], None],
        is_safe_to_move: Callable[[], bool]
    ):
        self._state = state
        self._motor_forward = motor_forward
        self._motor_backward = motor_backward
        self._motor_left = motor_left
        self._motor_right = motor_right
        self._motor_stop = motor_stop
        self._set_arrow = set_arrow
        self._is_safe = is_safe_to_move
        
        self._queue: Queue = Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_cmd: Optional[Command] = None
        self._abort_current = threading.Event()
    
    def start(self) -> None:
        """Start the command executor thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._executor_loop, daemon=True)
        self._thread.start()
        print("[Commands] Executor started")
    
    def stop(self) -> None:
        """Stop the command executor."""
        self._running = False
        self._abort_current.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        print("[Commands] Executor stopped")
    
    def submit(self, cmd_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a command for execution."""
        cmd = Command(cmd_type=cmd_type, params=params)
        
        # Handle immediate commands
        if cmd_type == "stop":
            self._abort_current.set()
            self._motor_stop()
            self._state.set_status(StateManager.STATUS_IDLE)
            return {"status": "ok", "message": "Stopped"}
        
        if cmd_type == "arrow":
            arrow_id = params.get("id", 1)
            state = params.get("state", "off") == "on"
            self._set_arrow(arrow_id, state)
            self._state.set_arrow(arrow_id, state)
            return {"status": "ok", "message": f"Arrow {arrow_id} {'on' if state else 'off'}"}
        
        if cmd_type == "arrows":
            pattern = params.get("pattern", "off")
            arrows_on = config.ARROW_PATTERNS.get(pattern, [])
            for i in range(1, 5):
                state = i in arrows_on
                self._set_arrow(i, state)
                self._state.set_arrow(i, state)
            return {"status": "ok", "message": f"Pattern '{pattern}' applied"}
        
        # Queue movement commands
        self._queue.put(cmd)
        self._state.set_pending_commands(self._queue.qsize())
        return {"status": "queued", "queue_size": self._queue.qsize()}
    
    def abort_all(self) -> None:
        """Abort current command and clear queue."""
        self._abort_current.set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break
        self._motor_stop()
        self._state.set_pending_commands(0)
        self._state.set_current_command(None)
    
    def _executor_loop(self) -> None:
        """Main executor loop."""
        while self._running:
            try:
                cmd = self._queue.get(timeout=0.1)
                self._state.set_pending_commands(self._queue.qsize())
            except Empty:
                continue
            
            self._abort_current.clear()
            self._current_cmd = cmd
            self._state.set_current_command({
                "type": cmd.cmd_type,
                "params": cmd.params
            })
            
            try:
                self._execute(cmd)
            except Exception as e:
                print(f"[Commands] Error executing {cmd.cmd_type}: {e}")
            finally:
                self._current_cmd = None
                self._state.set_current_command(None)
    
    def _execute(self, cmd: Command) -> None:
        """Execute a single command."""
        cmd_type = cmd.cmd_type
        params = cmd.params
        
        if cmd_type == "move":
            self._execute_move(params)
        elif cmd_type == "turn":
            self._execute_turn(params)
        elif cmd_type == "motors":
            self._execute_direct_motors(params)
        else:
            print(f"[Commands] Unknown command type: {cmd_type}")
    
    def _execute_move(self, params: Dict[str, Any]) -> None:
        """Execute a move command."""
        direction = params.get("direction", "forward")
        distance_cm = params.get("distance_cm", 10)
        speed = min(params.get("speed", 50), config.MAX_SPEED)
        
        # Estimate duration based on distance and speed
        # This is approximate - real odometry would be better
        duration_s = (distance_cm / 100.0) * (100.0 / speed) * 2.0
        duration_s = min(duration_s, config.DEFAULT_MOVE_TIMEOUT_S)
        
        print(f"[Commands] Move {direction} {distance_cm}cm at {speed}% for ~{duration_s:.1f}s")
        
        # Check safety before starting
        if direction == "forward" and not self._is_safe():
            print("[Commands] Move aborted - not safe")
            self._state.set_status(StateManager.STATUS_STOPPED)
            return
        
        self._state.set_status(StateManager.STATUS_MOVING)
        
        # Start movement
        if direction == "forward":
            self._motor_forward(speed)
        elif direction == "backward":
            self._motor_backward(speed)
        else:
            print(f"[Commands] Unknown direction: {direction}")
            return
        
        # Wait for duration or abort
        start_time = time.time()
        while time.time() - start_time < duration_s:
            if self._abort_current.is_set():
                print("[Commands] Move aborted")
                break
            if not self._is_safe() and direction == "forward":
                print("[Commands] Move stopped - obstacle detected")
                break
            time.sleep(0.05)
        
        self._motor_stop()
        self._state.set_status(StateManager.STATUS_IDLE)
    
    def _execute_turn(self, params: Dict[str, Any]) -> None:
        """Execute a turn command."""
        direction = params.get("direction", "left")
        degrees = params.get("degrees", 90)
        speed = min(params.get("speed", 50), config.MAX_SPEED)
        
        # Estimate duration based on degrees
        duration_s = (degrees / 360.0) * 4.0  # ~4s for full rotation
        duration_s = min(duration_s, config.DEFAULT_MOVE_TIMEOUT_S)
        
        print(f"[Commands] Turn {direction} {degrees}° at {speed}% for ~{duration_s:.1f}s")
        
        self._state.set_status(StateManager.STATUS_MOVING)
        
        if direction == "left":
            self._motor_left(speed)
        elif direction == "right":
            self._motor_right(speed)
        else:
            print(f"[Commands] Unknown direction: {direction}")
            return
        
        # Wait for duration or abort
        start_time = time.time()
        while time.time() - start_time < duration_s:
            if self._abort_current.is_set():
                print("[Commands] Turn aborted")
                break
            time.sleep(0.05)
        
        self._motor_stop()
        self._state.set_status(StateManager.STATUS_IDLE)
    
    def _execute_direct_motors(self, params: Dict[str, Any]) -> None:
        """Execute direct motor control (for testing)."""
        duration_ms = params.get("duration_ms", 1000)
        duration_s = duration_ms / 1000.0
        
        print(f"[Commands] Direct motor control for {duration_s:.1f}s")
        self._state.set_status(StateManager.STATUS_MOVING)
        
        # This would need direct motor access
        # For now, just wait
        start_time = time.time()
        while time.time() - start_time < duration_s:
            if self._abort_current.is_set():
                break
            time.sleep(0.05)
        
        self._motor_stop()
        self._state.set_status(StateManager.STATUS_IDLE)
