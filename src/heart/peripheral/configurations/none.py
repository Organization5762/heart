"""Peripheral configuration that disables all detection and graph nodes."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration


def configure() -> PeripheralConfiguration:
    """Return an empty peripheral detection plan for display-only runs."""

    return PeripheralConfiguration(detectors=(), graph_nodes=())
