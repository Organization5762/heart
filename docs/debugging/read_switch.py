import json

import serial

ser = serial.Serial("/dev/ttyACM0", 115200)

try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode("utf-8").rstrip()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                print(data)
                continue

            event_type = payload.get("event_type", "unknown")
            event_data = payload.get("data", {})
            print(f"{event_type}: {event_data}")
except KeyboardInterrupt:
    print("Program terminated")
finally:
    ser.close()
