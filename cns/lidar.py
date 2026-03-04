import serial
import threading
import time

class LidarReader(threading.Thread):
    def __init__(self, port='/dev/ttyS0', baudrate=115200, poll_interval=0.05):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.poll_interval = poll_interval
        self.distance_cm = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.ser = None

    def run(self):
        while not self._stop_event.is_set():
            try:
                if self.ser is None:
                    self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
                data = self.ser.read(9)
                if len(data) == 9 and data[0] == 0x59 and data[1] == 0x59:
                    dist_cm = data[2] + (data[3] << 8)
                    with self._lock:
                        self.distance_cm = dist_cm
                elif data and all(32 <= b <= 126 or b in (10, 13) for b in data):
                    line = data.decode(errors='ignore').strip()
                    if line and '.' in line:
                        try:
                            dist_m = float(line)
                            with self._lock:
                                self.distance_cm = dist_m * 100
                        except ValueError:
                            pass
                else:
                    line = self.ser.readline().decode(errors='ignore').strip()
                    if line and '.' in line:
                        try:
                            dist_m = float(line)
                            with self._lock:
                                self.distance_cm = dist_m * 100
                        except ValueError:
                            pass
            except serial.SerialException:
                if self.ser:
                    self.ser.close()
                    self.ser = None
                time.sleep(1)
            except Exception:
                time.sleep(1)
            time.sleep(self.poll_interval)

    def get_distance(self):
        with self._lock:
            return self.distance_cm

    def stop(self):
        self._stop_event.set()
        if self.ser:
            self.ser.close()
