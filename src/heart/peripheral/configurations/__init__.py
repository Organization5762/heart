"""Peripheral detection configuration modules."""

import itertools
import os
from typing import Any, Iterator

from heart.peripheral.compass import Compass
from heart.peripheral.configuration import GraphNodeFactory
from heart.peripheral.core import Peripheral
from heart.peripheral.drawing_pad import DrawingPad
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.heart_rates import HeartRateManager
from heart.peripheral.microphone import Microphone
from heart.peripheral.phone_text import PhoneText
from heart.peripheral.rubiks_connected_x import (
    RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR, RUBIKS_CONNECTED_X_AUTODETECT_ENV_VAR,
    RubiksConnectedXPeripheral)
from heart.peripheral.sensor import Accelerometer, FakeAccelerometer
from heart.peripheral.switch import BluetoothSwitch, FakeSwitch, Switch
from heart.peripheral.uwb import FakeUWBPositioning
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DISABLE_PHONE_TEXT_ENV_VAR = "HEART_DISABLE_PHONE_TEXT"

def _detect_switches() -> Iterator[Peripheral[Any]]:
    switches: list[Peripheral[Any]]
    if Configuration.use_mock_switch():
        logger.info("MOCK_SWITCH enabled; using fake switch")
        switches = list(FakeSwitch.detect())
    elif Configuration.is_pi() and not Configuration.is_x11_forward():
        logger.info("Detecting switches")
        switches = [
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

def _switch_detection_node(
    *,
    start_immediately: bool,
    on_detect: Any | None,
) -> Any:
    return Switch.detection_node(
        detector=_detect_switches,
        spawn_sources=True,
        on_detect=on_detect,
        start_immediately=start_immediately,
    )

def _switch_graph_nodes() -> tuple[GraphNodeFactory, ...]:
    if Configuration.use_mock_switch():
        return ()
    if Configuration.is_pi() and not Configuration.is_x11_forward():
        return (_switch_detection_node,)
    return ()

def _detect_phone_text() -> Iterator[Peripheral[Any]]:
    if os.environ.get(DISABLE_PHONE_TEXT_ENV_VAR) == "1":
        logger.info("PhoneText detection disabled via %s", DISABLE_PHONE_TEXT_ENV_VAR)
        return
    yield from itertools.chain(PhoneText.detect())

def _detect_rubiks_connected_x() -> Iterator[Peripheral[Any]]:
    configured_address = os.environ.get(RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR)
    autodetect_enabled = os.environ.get(RUBIKS_CONNECTED_X_AUTODETECT_ENV_VAR)
    if not configured_address and not autodetect_enabled:
        return
    yield from itertools.chain(RubiksConnectedXPeripheral.detect())

def _rubiks_connected_x_detection_node(
    *,
    start_immediately: bool,
    on_detect: Any | None,
) -> Any:
    return RubiksConnectedXPeripheral.detection_node(
        detector=_detect_rubiks_connected_x,
        spawn_sources=True,
        on_detect=on_detect,
        start_immediately=start_immediately,
    )

def _rubiks_connected_x_graph_nodes() -> tuple[GraphNodeFactory, ...]:
    return (_rubiks_connected_x_detection_node,)

def _detect_sensors() -> Iterator[Peripheral[Any]]:
    if Configuration.is_pi() and not Configuration.is_x11_forward():
        yield from itertools.chain(Compass.detect())
    else:
        yield from FakeAccelerometer.detect()

def _accelerometer_detection_node(
    *,
    start_immediately: bool,
    on_detect: Any | None,
) -> Any:
    return Accelerometer.detection_node(
        spawn_sources=True,
        on_detect=on_detect,
        start_immediately=start_immediately,
    )

def _accelerometer_graph_nodes() -> tuple[GraphNodeFactory, ...]:
    if Configuration.is_pi() and not Configuration.is_x11_forward():
        return (_accelerometer_detection_node,)
    return ()

def _detect_gamepads() -> Iterator[Peripheral[Any]]:
    yield from itertools.chain(Gamepad.detect())

def _detect_heart_rate_sensor() -> Iterator[Peripheral[Any]]:
    yield from itertools.chain(HeartRateManager.detect())

def _heart_rate_detection_node(
    *,
    start_immediately: bool,
    on_detect: Any | None,
) -> Any:
    return HeartRateManager.detection_node(
        spawn_sources=True,
        on_detect=on_detect,
        start_immediately=start_immediately,
    )

def _heart_rate_graph_nodes() -> tuple[GraphNodeFactory, ...]:
    return (_heart_rate_detection_node,)

def _detect_microphones() -> Iterator[Peripheral[Any]]:
    yield from itertools.chain(Microphone.detect())

def _microphone_detection_node(
    *,
    start_immediately: bool,
    on_detect: Any | None,
) -> Any:
    return Microphone.detection_node(
        spawn_sources=True,
        on_detect=on_detect,
        start_immediately=start_immediately,
    )

def _microphone_graph_nodes() -> tuple[GraphNodeFactory, ...]:
    return (_microphone_detection_node,)

def _detect_drawing_pads() -> Iterator[Peripheral[Any]]:
    yield from itertools.chain(DrawingPad.detect())

def _detect_radios() -> Iterator[Peripheral[Any]]:
    from heart.peripheral.radio import RadioPeripheral

    yield from itertools.chain(RadioPeripheral.detect())

def _radio_detection_node(
    *,
    start_immediately: bool,
    on_detect: Any | None,
) -> Any:
    from heart.peripheral.radio import RadioPeripheral

    return RadioPeripheral.detection_node(
        spawn_sources=True,
        on_detect=on_detect,
        start_immediately=start_immediately,
    )

def _radio_graph_nodes() -> tuple[GraphNodeFactory, ...]:
    return (_radio_detection_node,)

def _manyfold_graph_nodes() -> tuple[GraphNodeFactory, ...]:
    return (
        *_switch_graph_nodes(),
        *_accelerometer_graph_nodes(),
        *_heart_rate_graph_nodes(),
        *_radio_graph_nodes(),
        *_rubiks_connected_x_graph_nodes(),
        *_microphone_graph_nodes(),
    )

def _detect_uwb_position() -> Iterator[Peripheral[Any]]:
    yield from itertools.chain(FakeUWBPositioning.detect())
