"""Peripheral detection configuration for Rubik's Connected X visualizer runs."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configurations import (
    _detect_rubiks_connected_x,
    _detect_sensors,
    _detect_switches,
)


def configure() -> PeripheralConfiguration:
    """Return a minimal detection plan for Rubik's Connected X visualizer runs."""

    detectors = (
        _detect_switches,
        _detect_sensors,
        _detect_rubiks_connected_x,
    )
    return PeripheralConfiguration(detectors=detectors)
