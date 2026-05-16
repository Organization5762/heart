"""Default peripheral detection configuration."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configurations import _manyfold_graph_nodes


def configure() -> PeripheralConfiguration:
    """Return the default detection plan for ``manager``."""

    return PeripheralConfiguration(
        detectors=(), graph_nodes=_manyfold_graph_nodes()
    )
