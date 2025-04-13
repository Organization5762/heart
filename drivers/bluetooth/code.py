import board
import digitalio
import time
import random

from adafruit_ble import BLERadio
from adafruit_ble.services.nordic import UARTService
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
import json
from collections import deque

DELAY_BETWEEN_MESSAGES = 0.1
MINIMUM_LIGHT_ON_SECONDS = 0.05

END_OF_MESSAGE_DELIMETER = "\n"
ENCODING = "utf-8"

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
# Set LED to True to note it is booting up
led.value = True

# Setup all the bluetooth mumbo-jumbo
ble = BLERadio()
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

i = 0
def gather_state() -> list[dict[str, str]]:
    global i
    i += 1
    print(i)
    return [
        {
            "event_type": "rotation",
            "data": i
        }
    ]

###
###
# Core loop
###
###
previous_message = None
# Maybe we want this? I'm still trying to figure out how wonky this whole "missing messages" thing is going to be
not_connected_buffer = deque([], 10)

if not ble.advertising:
    ble.start_advertising(advertisement)

while True:
    led.value = True

    if not ble.advertising:
        ble.start_advertising(advertisement)

    if ble.connected:
        # We're connected, make sure the buffer is drained as the first priority
        while not not_connected_buffer:
            uart.write(not_connected_buffer.popleft().encode(ENCODING))

        current = gather_state()
        msg = json.dumps(current) + END_OF_MESSAGE_DELIMETER
        if msg != previous_message:
            uart.write(msg.encode(ENCODING))
    else:
        current = gather_state()
        msg = json.dumps(current) + END_OF_MESSAGE_DELIMETER
        if msg != previous_message:
            not_connected_buffer.append(msg)

    previous_message = current

    led.value = False
    time.sleep(DELAY_BETWEEN_MESSAGES)