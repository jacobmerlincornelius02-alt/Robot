import serial
import time

ser = serial.Serial('/dev/ttyS0', 115200, timeout=1)
try:
    while True:
        # time.sleep(0.2)
        try:
            data = ser.read(9)
            # Check for binary frame (starts with 0x59 0x59)
            if len(data) == 9 and data[0] == 0x59 and data[1] == 0x59:
                dist_cm = data[2] + (data[3] << 8)
                print(f"Distance: {dist_cm} cm (binary)")
            # Check for ASCII PIX format (e.g., b'1.23\r\n')
            elif data and all(32 <= b <= 126 or b in (10, 13) for b in data):
                line = data.decode(errors='ignore').strip()
                if line and '.' in line:
                    try:
                        dist_m = float(line)
                        print(f"Distance: {dist_m*100:.2f} cm (ASCII)")
                    except ValueError:
                        pass
            else:
                # Try to read a line in case of ASCII format
                line = ser.readline().decode(errors='ignore').strip()
                if line and '.' in line:
                    try:
                        dist_m = float(line)
                        print(f"Distance: {dist_m*100:.2f} cm (ASCII)")
                    except ValueError:
                        pass
        except serial.SerialException as e:
            print(f"Serial error: {e}. Attempting to reset port.")
            ser.close()
            time.sleep(1)
            ser.open()
except KeyboardInterrupt:
    print("Stopped by user.")
finally:
    ser.close()
