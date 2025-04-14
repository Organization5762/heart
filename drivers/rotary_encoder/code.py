import rotaryio
import board
from digitalio import DigitalInOut, Direction, Pull
import time  # Import time module for tracking button press duration

# Initialize the rotary encoder
enc = rotaryio.IncrementalEncoder(
    pin_a=board.ROTA,
    pin_b=board.ROTB,
)
last_position = None

# Variables to track button press timing and state
press_start = None         # Holds the time when the button was first pressed
long_pressed_sent = False  # Flags whether a long-press event has been sent

# Initialize the button switch
switch = DigitalInOut(board.SWITCH)
switch.direction = Direction.INPUT
switch.pull = Pull.DOWN

# Helper function to produce JSON-formatted messages
def form_json(name: str, data: int):
    return '{"event_type": "' + name + '", "data": ' + str(data) + '}'

while True:
    # Handle rotary encoder rotations:
    position = enc.position
    if last_position is None or position != last_position:
        print(form_json("rotation", position))
    last_position = position

    # Read the current state of the button
    switch_value = switch.value

    if switch_value:
        # Button is pressed
        if press_start is None:
            # Button has just been pressed: record the current time
            press_start = time.monotonic()
        else:
            # Button is still held down; check if it qualifies as a long press
            if not long_pressed_sent and (time.monotonic() - press_start) >= 0.75:
                # 0.75 seconds have passed – define this as a long press.
                print(form_json("button.long_press", 1))
                long_pressed_sent = True
    else:
        # Button is released
        if press_start is not None:
            if not long_pressed_sent:
                print(form_json("button.press", 1))
                
            press_start = None
            long_pressed_sent = False
