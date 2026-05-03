"""Default peripheral detection configuration."""

from __future__ import annotations

from heart.peripheral.configuration import (DetectorFactory,
                                            PeripheralConfiguration)
from heart.peripheral.configurations import (_detect_switches,
                                             _manyfold_graph_nodes,
                                             _switch_graph_nodes)


def configure() -> PeripheralConfiguration:
    """Return the default detection plan for ``manager``."""

    detectors: list[DetectorFactory] = []
    if not _switch_graph_nodes():
        detectors.insert(0, _detect_switches)
    return PeripheralConfiguration(
        detectors=tuple(detectors), graph_nodes=_manyfold_graph_nodes()
    )
