"""Peripheral detection configuration for Rubik's Connected X visualizer runs."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configurations import (_detect_sensors, _detect_switches,
                                             _rubiks_connected_x_graph_nodes)


def configure() -> PeripheralConfiguration:
    """Return a minimal detection plan for Rubik's Connected X visualizer runs."""

    detectors = (
        _detect_switches,
        _detect_sensors,
    )
    return PeripheralConfiguration(
        detectors=detectors,
        graph_nodes=_rubiks_connected_x_graph_nodes(),
    )
