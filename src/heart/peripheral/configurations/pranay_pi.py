"""Minimal peripheral configuration for direct Pranay rendering on Raspberry Pi."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configurations import _detect_switches


def configure() -> PeripheralConfiguration:
    """Return the minimal peripheral plan needed to boot the Pranay scene."""

    return PeripheralConfiguration(detectors=(_detect_switches,))
