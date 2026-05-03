"""Default peripheral detection configuration."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configurations import (_detect_drawing_pads,
                                             _detect_gamepads,
                                             _detect_phone_text,
                                             _detect_sensors,
                                             _detect_uwb_position,
                                             _manyfold_graph_nodes,
                                             _switch_graph_nodes)


def configure() -> PeripheralConfiguration:
    """Return the default detection plan for ``manager``."""

    detectors = [
        _detect_sensors,
        _detect_gamepads,
        _detect_phone_text,
        _detect_drawing_pads,
        _detect_uwb_position
    ]
    if not _switch_graph_nodes():
        from heart.peripheral.configurations import _detect_switches

        detectors.insert(0, _detect_switches)
    return PeripheralConfiguration(detectors=tuple(detectors), graph_nodes=_manyfold_graph_nodes())
