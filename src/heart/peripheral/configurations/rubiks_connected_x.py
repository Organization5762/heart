"""Peripheral detection configuration for Rubik's Connected X visualizer runs."""

from __future__ import annotations

from heart.peripheral.configuration import (DetectorFactory,
                                            PeripheralConfiguration)
from heart.peripheral.configurations import (_detect_switches,
                                             _fake_accelerometer_graph_nodes,
                                             _rubiks_connected_x_graph_nodes,
                                             _switch_graph_nodes)


def configure() -> PeripheralConfiguration:
    """Return a minimal detection plan for Rubik's Connected X visualizer runs."""

    detectors: list[DetectorFactory] = []
    switch_graph_nodes = _switch_graph_nodes()
    graph_nodes = (
        *switch_graph_nodes,
        *_fake_accelerometer_graph_nodes(),
        *_rubiks_connected_x_graph_nodes(),
    )
    if not switch_graph_nodes:
        detectors.insert(0, _detect_switches)
    return PeripheralConfiguration(
        detectors=tuple(detectors),
        graph_nodes=graph_nodes,
    )
