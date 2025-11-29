"""Peripheral detection configuration modules."""

import itertools
from typing import Iterator

from heart.environment import logger
from heart.peripheral.compass import Compass
from heart.peripheral.core import Peripheral
from heart.peripheral.drawing_pad import DrawingPad
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.heart_rates import HeartRateManager
from heart.peripheral.microphone import Microphone
from heart.peripheral.phone_text import PhoneText
from heart.peripheral.radio import RadioPeripheral
from heart.peripheral.sensor import Accelerometer
from heart.peripheral.switch import BluetoothSwitch, FakeSwitch, Switch
from heart.utilities.env import Configuration


def _detect_switches() -> Iterator[Peripheral]:
    if Configuration.is_pi() and not Configuration.is_x11_forward():
        logger.info("Detecting switches")
        switches: list[Peripheral] = [
            *Switch.detect(),
            *BluetoothSwitch.detect(),
        ]
        logger.info("Found %d switches", len(switches))
        if len(switches) == 0:
            logger.warning("No switches found")
            switches = list(FakeSwitch.detect())
    else:
        logger.info("Not running on pi, using fake switch")
        switches = list(FakeSwitch.detect())

    for switch in switches:
        logger.info("Adding switch - %s", switch)
        yield switch

def _detect_phone_text() -> Iterator[Peripheral]:
    yield from itertools.chain(PhoneText.detect())

def _detect_sensors() -> Iterator[Peripheral]:
    yield from itertools.chain(Accelerometer.detect(), Compass.detect())

def _detect_gamepads() -> Iterator[Peripheral]:
    yield from itertools.chain(Gamepad.detect())

def _detect_heart_rate_sensor() -> Iterator[Peripheral]:
    yield from itertools.chain(HeartRateManager.detect())

def _detect_microphones() -> Iterator[Peripheral]:
    yield from itertools.chain(Microphone.detect())

def _detect_drawing_pads() -> Iterator[Peripheral]:
    yield from itertools.chain(DrawingPad.detect())

def _detect_radios() -> Iterator[Peripheral]:
    yield from itertools.chain(RadioPeripheral.detect())