# https://docs.circuitpython.org/en/latest/shared-bindings/rotaryio/index.html
# This is code loaded onto the the little Rotary encoder
# TODO (lampe): Send button press
import rotaryio
import time
import board

# TODO (lampe): Need to send the button press + disambiguate button presses from rotary turns.
# Probably use JSON + events?

# I got ROTA and ROTB just by doing dir(board)
enc = rotaryio.IncrementalEncoder(
    pin_a=board.ROTA,
    pin_b=board.ROTB,
)
last_position = None
while True:
    position = enc.position
    if last_position is None or position != last_position:
        print(position)
    last_position = position