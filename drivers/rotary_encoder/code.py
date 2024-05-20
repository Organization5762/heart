# https://docs.circuitpython.org/en/latest/shared-bindings/rotaryio/index.html
# This is code loaded onto the the little Rotary encoder
# TODO (lampe): Send button press
# TODO (lampe): Need to send the button press + disambiguate button presses from rotary turns.
# Probably use JSON + events?
# import json
import rotaryio
import board
from digitalio import DigitalInOut, Direction, Pull

# I got ROTA and ROTB just by doing dir(board)
enc = rotaryio.IncrementalEncoder(
    pin_a=board.ROTA,
    pin_b=board.ROTB,
)
last_position = None
last_switch_value = None


switch = DigitalInOut(board.SWITCH)
switch.direction = Direction.INPUT
switch.pull = Pull.DOWN

while True:
    position = enc.position
    switch_value = switch.value
    if last_position is None or position != last_position:
        print(f"ROTATION: {position}")
    
    if last_switch_value is None or switch_value != last_switch_value:
        print(f"SWITCH: {switch.value}")
        
    last_position = position
    last_switch_value = switch_value
