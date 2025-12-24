import json

import serial

ser = serial.Serial("/dev/ttyACM0", 115200)

try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode("utf-8").rstrip()
            if data.startswith("{"):
                payload = json.loads(data)
                event_type = payload.get("event_type")
                producer_id = payload.get("producer_id")
                event_data = payload.get("data")
                print(f"{event_type} (producer={producer_id}): {event_data}")
            else:
                print(data)
except KeyboardInterrupt:
    print("Program terminated")
finally:
    ser.close()
