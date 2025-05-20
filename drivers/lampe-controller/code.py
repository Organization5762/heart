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
from heart.firmware_io import constants, rotary_encoder, bluetooth

MINIMUM_LIGHT_ON_SECONDS = 0.05

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = True

i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)
# FeatherWings (the little add-on boards) almost always have ADDR → GND, so you’d use 0x48.
# If you’re using a loose breakout and you tied its ADDR pin to VDD, then the 0x49 default in your code is correct.
seesaw = adafruit_seesaw.seesaw.Seesaw(i2c, 0x49)

encoder = adafruit_seesaw.rotaryio.IncrementalEncoder(seesaw)
seesaw.pin_mode(24, seesaw.INPUT_PULLUP)

encoders = [adafruit_seesaw.rotaryio.IncrementalEncoder(seesaw, n) for n in range(4)]
switches = [adafruit_seesaw.digitalio.DigitalIO(seesaw, pin) for pin in (12, 14, 17, 9)]
for switch in switches:
    switch.switch_to_input(digitalio.Pull.UP)

handlers = [
    rotary_encoder.RotaryEncoderHandler(encoders[0], switches[0], 0),
    rotary_encoder.RotaryEncoderHandler(encoders[1], switches[1], 1),
    rotary_encoder.RotaryEncoderHandler(encoders[2], switches[2], 2),
    rotary_encoder.RotaryEncoderHandler(encoders[3], switches[3], 3),
]

seesaw = rotary_encoder.Seesaw(handlers)

while True:
    for event in seesaw.handle():
        print("Sending ", event)
        bluetooth.send([event])
        print("Sent ", event)
    