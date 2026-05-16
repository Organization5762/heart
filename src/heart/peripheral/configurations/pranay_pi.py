"""Minimal peripheral configuration for direct Pranay rendering on Raspberry Pi."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configurations import _switch_graph_nodes


def configure() -> PeripheralConfiguration:
    """Return the minimal peripheral plan needed to boot the Pranay scene."""

    return PeripheralConfiguration(detectors=(), graph_nodes=_switch_graph_nodes())
