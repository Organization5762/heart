import board
import digitalio
import time
import random
import adafruit_seesaw.seesaw
import adafruit_seesaw.rotaryio
import adafruit_seesaw.digitalio
import busio
from adafruit_ble import BLERadio
from adafruit_ble.services.nordic import UARTService
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
import json
from collections import deque

DELAY_BETWEEN_MESSAGES = 0.1
MINIMUM_LIGHT_ON_SECONDS = 0.05

END_OF_MESSAGE_DELIMETER = "\n"
ENCODING = "utf-8"

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = True

# FeatherWings (the little add-on boards) almost always have ADDR → GND, so you’d use 0x48.
# If you’re using a loose breakout and you tied its ADDR pin to VDD, then the 0x49 default in your code is correct.
i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)
seesaw = adafruit_seesaw.seesaw.Seesaw(i2c, 0x48)

encoder = adafruit_seesaw.rotaryio.IncrementalEncoder(seesaw)
seesaw.pin_mode(24, seesaw.INPUT_PULLUP)

encoders = [adafruit_seesaw.rotaryio.IncrementalEncoder(seesaw, n) for n in range(4)]
switches = [adafruit_seesaw.digitalio.DigitalIO(seesaw, pin) for pin in (12, 14, 17, 9)]
for switch in switches:
    switch.switch_to_input(digitalio.Pull.UP)  # input & pullup!

last_positions = [-1] * 4
while True:
    positions = [encoder.position for encoder in encoders]
    print(positions)
    for n, rotary_pos in enumerate(positions):
        if rotary_pos != last_positions[n]:
            if switches[n].value:  # Change the LED color if switch is not pressed
                if (
                    rotary_pos > last_positions[n]
                ):  # Advance forward through the colorwheel.
                    colors[n] += 8
                else:
                    colors[n] -= 8  # Advance backward through the colorwheel.
                colors[n] = (colors[n] + 256) % 256  # wrap around to 0-256
            # Set last position to current position after evaluating
            print(f"Rotary #{n}: {rotary_pos}")
            last_positions[n] = rotary_pos

    time.sleep(0.1)


# # Setup all the bluetooth mumbo-jumbo
# ble = BLERadio()
# uart = UARTService()
# advertisement = ProvideServicesAdvertisement(uart)

# i = 0
# def gather_state() -> list[dict[str, str]]:
#     global i
#     i += 1
#     print(i)
#     return [
#         {
#             "event_type": "rotation",
#             "data": i
#         }
#     ]

# ###
# ###
# # Core loop
# ###
# ###
# previous_message = None
# # Maybe we want this? I'm still trying to figure out how wonky this whole "missing messages" thing is going to be
# not_connected_buffer = deque([], 10)

# if not ble.advertising:
#     ble.start_advertising(advertisement)

# while True:
#     led.value = True

#     if not ble.advertising:
#         ble.start_advertising(advertisement)

#     if ble.connected:
#         # We're connected, make sure the buffer is drained as the first priority
#         while not not_connected_buffer:
#             uart.write(not_connected_buffer.popleft().encode(ENCODING))

#         current = gather_state()
#         msg = json.dumps(current) + END_OF_MESSAGE_DELIMETER
#         if msg != previous_message:
#             uart.write(msg.encode(ENCODING))
#     else:
#         current = gather_state()
#         msg = json.dumps(current) + END_OF_MESSAGE_DELIMETER
#         if msg != previous_message:
#             not_connected_buffer.append(msg)

#     previous_message = current

#     led.value = False
#     time.sleep(DELAY_BETWEEN_MESSAGES)