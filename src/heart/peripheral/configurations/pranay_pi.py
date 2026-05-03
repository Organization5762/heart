"""Minimal peripheral configuration for direct Pranay rendering on Raspberry Pi."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configurations import (_detect_switches,
                                             _switch_graph_nodes)


def configure() -> PeripheralConfiguration:
    """Return the minimal peripheral plan needed to boot the Pranay scene."""

    graph_nodes = _switch_graph_nodes()
    detectors = () if graph_nodes else (_detect_switches,)
    return PeripheralConfiguration(detectors=detectors, graph_nodes=graph_nodes)
