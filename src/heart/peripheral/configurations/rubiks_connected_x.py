"""Peripheral detection configuration for Rubik's Connected X visualizer runs."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configurations import (_fake_accelerometer_graph_nodes,
                                             _rubiks_connected_x_graph_nodes,
                                             _switch_graph_nodes)


def configure() -> PeripheralConfiguration:
    """Return a minimal detection plan for Rubik's Connected X visualizer runs."""

    graph_nodes = (
        *_switch_graph_nodes(),
        *_fake_accelerometer_graph_nodes(),
        *_rubiks_connected_x_graph_nodes(),
    )
    return PeripheralConfiguration(
        detectors=(),
        graph_nodes=graph_nodes,
    )
