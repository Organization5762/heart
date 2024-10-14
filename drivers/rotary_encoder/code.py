# https://docs.circuitpython.org/en/latest/shared-bindings/rotaryio/index.html
# This is code loaded onto the the little Rotary encoder
# TODO (lampe): Send button press
# TODO (lampe): Need to send the button press + disambiguate button presses from rotary turns.
# Probably use JSON + events?
# import json
import time
import rotaryio
import board
from digitalio import DigitalInOut, Direction, Pull

# I got ROTA and ROTB just by doing dir(board)
enc = rotaryio.IncrementalEncoder(
    pin_a=board.ROTA,
    pin_b=board.ROTB,
)
last_position = None

has_sent_this_input = False


switch = DigitalInOut(board.SWITCH)
switch.direction = Direction.INPUT
switch.pull = Pull.DOWN


def form_json(name: str, data: int):
    return '{"event_type": "' + name + '", "data": ' + str(data) + '}'


while True:
    position = enc.position
    switch_value = switch.value
    if last_position is None or position != last_position:
        print(form_json("rotation", position))
            
    if switch_value and not has_sent_this_input:
        # Send 1 instead of true so: (1) It can be added (2) we don't need to convert to JSON bool
        print(form_json("button", 1))
        has_sent_this_input = True
    elif not switch_value and has_sent_this_input:
        # Switch it back, as the button has become undepressed
        has_sent_this_input = False
        
    last_position = position
