# https://docs.circuitpython.org/en/latest/shared-bindings/rotaryio/index.html

import rotaryio
import board
from digitalio import DigitalInOut, Direction, Pull
from heart.firmware_io import rotary_encoder

# I got ROTA and ROTB just by doing dir(board)
enc = rotaryio.IncrementalEncoder(
    pin_a=board.ROTA,
    pin_b=board.ROTB,
)

switch = DigitalInOut(board.SWITCH)
switch.direction = Direction.INPUT
switch.pull = Pull.DOWN

while True:
    handler = rotary_encoder.RotaryEncoderHandler(enc, switch, 0)
    for event in handler.handle():
        print(event)
