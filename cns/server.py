#!/usr/bin/env python3
"""HTTP Server for the robot CNS.

This provides the API that the brain (Copilot) uses to control the robot.
"""

import time
from flask import Flask, jsonify, request

# Import hardware library
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import PiMotor
from cns import config
from cns.state import StateManager
from cns.safety import SafetySystem
from cns.commands import CommandExecutor


class CNSServer:
    """Central Nervous System server."""
    
    def __init__(self):
        self.app = Flask(__name__)
        
        # Initialize hardware
        print("[CNS] Initializing hardware...")
        self._init_hardware()
        
        # Initialize state manager
        self.state = StateManager()
        
        # Initialize safety system
        self.safety = SafetySystem(
            state=self.state,
            stop_motors_callback=self._stop_all_motors,
            read_ultrasonic_callback=self._read_ultrasonic
        )
        
        # Initialize command executor
        self.commands = CommandExecutor(
            state=self.state,
            motor_forward=self._motor_forward,
            motor_backward=self._motor_backward,
            motor_left=self._motor_left,
            motor_right=self._motor_right,
            motor_stop=self._stop_all_motors,
            set_arrow=self._set_arrow,
            is_safe_to_move=self._is_safe_to_move
        )
        
        # Register routes
        self._register_routes()
        
        print("[CNS] Initialization complete")
    
    def _init_hardware(self):
        """Initialize motors, arrows, and sensors."""
        # Motors
        self.m1 = PiMotor.Motor("MOTOR1", 1)
        self.m2 = PiMotor.Motor("MOTOR2", 1)
        self.m3 = PiMotor.Motor("MOTOR3", 1)
        self.m4 = PiMotor.Motor("MOTOR4", 1)
        self.motors = PiMotor.LinkedMotors(self.m1, self.m2, self.m3, self.m4)
        
        # Arrows (reuse from motors to avoid pin conflicts)
        self.arrows = {
            1: self.m4.arrow,  # ab
            2: self.m3.arrow,  # al
            3: self.m2.arrow,  # af
            4: self.m1.arrow   # ar
        }
        
        # Ultrasonic sensor
        try:
            self.ultrasonic = PiMotor.Sensor("ULTRASONIC", config.COLLISION_DISTANCE_CM)
            self._has_ultrasonic = True
        except Exception as e:
            print(f"[CNS] Warning: Ultrasonic sensor not available: {e}")
            self._has_ultrasonic = False
        
        print("[CNS] Hardware initialized")
    
    def _register_routes(self):
        """Register Flask routes."""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            return jsonify({
                "status": "ok",
                "timestamp": time.time(),
                "uptime": time.time() - self._start_time if hasattr(self, '_start_time') else 0
            })
        
        @self.app.route('/state', methods=['GET'])
        def get_state():
            # Heartbeat on state request
            self.state.heartbeat()
            return jsonify(self.state.get_state())
        
        @self.app.route('/sensors', methods=['GET'])
        def get_sensors():
            self.state.heartbeat()
            return jsonify(self.state.get_sensors())
        
        @self.app.route('/command', methods=['POST'])
        def post_command():
            self.state.heartbeat()
            
            if self.safety.is_emergency():
                return jsonify({
                    "status": "error",
                    "message": "Emergency stop active. Call /reset first."
                }), 400
            
            data = request.get_json()
            if not data or 'cmd' not in data:
                return jsonify({
                    "status": "error",
                    "message": "Missing 'cmd' field"
                }), 400
            
            cmd_type = data.pop('cmd')
            result = self.commands.submit(cmd_type, data)
            return jsonify(result)
        
        @self.app.route('/stop', methods=['POST'])
        def stop():
            self.state.heartbeat()
            self.commands.submit("stop", {})
            return jsonify({"status": "ok", "message": "Stopped"})
        
        @self.app.route('/emergency', methods=['POST'])
        def emergency():
            self.safety.emergency_stop()
            self.commands.abort_all()
            return jsonify({"status": "ok", "message": "Emergency stop activated"})
        
        @self.app.route('/reset', methods=['POST'])
        def reset():
            self.safety.reset_emergency()
            return jsonify({"status": "ok", "message": "Emergency reset"})
        
        @self.app.route('/heartbeat', methods=['POST'])
        def heartbeat():
            self.state.heartbeat()
            return jsonify({"status": "ok", "timestamp": time.time()})
    
    # Hardware control methods
    
    def _stop_all_motors(self):
        """Stop all motors immediately."""
        try:
            self.motors.stop()
        except Exception as e:
            print(f"[CNS] Error stopping motors: {e}")
    
    def _motor_forward(self, speed: int):
        """Move forward at given speed."""
        self._set_arrow(3, True)  # Forward arrow
        self.motors.forward(speed)
    
    def _motor_backward(self, speed: int):
        """Move backward at given speed."""
        self._set_arrow(1, True)  # Back arrow
        self.motors.reverse(speed)
    
    def _motor_left(self, speed: int):
        """Turn left at given speed."""
        self._set_arrow(2, True)  # Left arrow
        self.m1.stop()
        self.m2.stop()
        self.m3.forward(speed)
        self.m4.forward(speed)
    
    def _motor_right(self, speed: int):
        """Turn right at given speed."""
        self._set_arrow(4, True)  # Right arrow
        self.m1.forward(speed)
        self.m2.forward(speed)
        self.m3.stop()
        self.m4.stop()
    
    def _set_arrow(self, arrow_id: int, state: bool):
        """Set arrow LED state."""
        if arrow_id in self.arrows:
            if state:
                self.arrows[arrow_id].on()
            else:
                self.arrows[arrow_id].off()
    
    def _read_ultrasonic(self):
        """Read ultrasonic sensor distance."""
        if not self._has_ultrasonic:
            return None
        
        try:
            self.ultrasonic.trigger()
            return self.ultrasonic.lastRead
        except Exception as e:
            print(f"[CNS] Error reading ultrasonic: {e}")
            return None
    
    def _is_safe_to_move(self):
        """Check if it's safe to move forward."""
        if self.safety.is_emergency():
            return False
        if self.state.is_collision_imminent():
            return False
        return True
    
    def run(self):
        """Start the CNS server."""
        self._start_time = time.time()
        
        # Start safety system
        self.safety.start()
        
        # Start command executor
        self.commands.start()
        
        # Initial heartbeat
        self.state.heartbeat()
        
        print(f"[CNS] Server starting on http://{config.HOST}:{config.PORT}")
        
        try:
            self.app.run(
                host=config.HOST,
                port=config.PORT,
                threaded=True,
                debug=False
            )
        finally:
            self.safety.stop()
            self.commands.stop()
            self._stop_all_motors()


def main():
    """Main entry point."""
    server = CNSServer()
    server.run()


if __name__ == '__main__':
    main()
