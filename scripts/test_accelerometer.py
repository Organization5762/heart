import time

from serial.serialutil import SerialException
from heart.peripherial.manager import PeripherialManager
from heart.peripherial.sensor import Accelerometer
import serial

m = PeripherialManager()
d = m.detect()

accelerometers: list[Accelerometer] = [x for x in m.peripherials if isinstance(x, Accelerometer)]
assert len(accelerometers) == 1, f"Found {len(accelerometers)}"
accelerometer = accelerometers[0]
# s = accelerometer._connect_to_ser()
# s = serial.Serial("/dev/serial/by-id/usb-Adafruit_KB2040_DF62585783393B33-if00", 115200)

s = accelerometer._connect_to_ser()

print("Starting loop")
while True:
    try:
        datas = s.readlines(s.in_waiting or 1)
        for data in datas:
            accelerometer._process_data(data)
        
        print("\n\n")
        print(accelerometer.acceleration_value)
        print(f"\nX Jerk: {accelerometer.x_distribution.jerk()}")
    except SerialException as e:
        pass