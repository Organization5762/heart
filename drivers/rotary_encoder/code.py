# https://docs.circuitpython.org/en/latest/shared-bindings/rotaryio/index.html

import rotaryio
import board
from digitalio import DigitalInOut, Direction, Pull
import time
from heart.firmware_io import constants

LONG_PRESS_DURATION_SECONDS = 0.5

# I got ROTA and ROTB just by doing dir(board)
enc = rotaryio.IncrementalEncoder(
    pin_a=board.ROTA,
    pin_b=board.ROTB,
)
last_position = None

# Variables to track button press timing and state
press_start = None
long_pressed_sent = False

switch = DigitalInOut(board.SWITCH)
switch.direction = Direction.INPUT
switch.pull = Pull.DOWN

def form_json(name: str, data: int):
    return '{"event_type": "' + name + '", "data": ' + str(data) + '}'

while True:
    # Handle rotary encoder rotations:
    position = enc.position
    if last_position is None or position != last_position:
        print(form_json(constants.SWITCH_ROTATION, position))
    last_position = position

    # Read the current state of the button
    switch_value = switch.value

    if switch_value:
        # Button just pressed
        if press_start is None:
            press_start = time.monotonic()
        else:
            # Button is still held down; check if it qualifies as a long press
            if not long_pressed_sent and (time.monotonic() - press_start) >= LONG_PRESS_DURATION_SECONDS:
                print(form_json(constants.BUTTON_LONG_PRESS, 1))
                long_pressed_sent = True
    else:
        # Button is released
        if press_start is not None:
            if not long_pressed_sent:
                print(form_json(constants.BUTTON_PRESS, 1))

            press_start = None
            long_pressed_sent = False
