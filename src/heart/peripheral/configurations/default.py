"""Default peripheral detection configuration."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configurations import (_detect_drawing_pads,
                                             _detect_gamepads,
                                             _detect_heart_rate_sensor,
                                             _detect_phone_text,
                                             _detect_sensors, _detect_switches,
                                             _detect_uwb_position,
                                             _manyfold_graph_nodes)


def configure() -> PeripheralConfiguration:
    """Return the default detection plan for ``manager``."""

    detectors = (
        _detect_switches,
        _detect_sensors,
        _detect_gamepads,
        _detect_heart_rate_sensor,
        _detect_phone_text,
        _detect_drawing_pads,
        _detect_uwb_position
    )
    return PeripheralConfiguration(detectors=detectors, graph_nodes=_manyfold_graph_nodes())
