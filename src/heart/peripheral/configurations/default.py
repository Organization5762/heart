"""Default peripheral detection configuration."""

from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration

if False:  # pragma: no cover - typing aid
    from heart.peripheral.core.manager import PeripheralManager


def configure(manager: "PeripheralManager") -> PeripheralConfiguration:
    """Return the default detection plan for ``manager``."""

    detectors = (
        manager._detect_switches,
        manager._detect_sensors,
        manager._detect_gamepads,
        manager._detect_heart_rate_sensor,
        manager._detect_phone_text,
        manager._detect_microphones,
        manager._detect_drawing_pads,
        manager._detect_radios,
    )
    return PeripheralConfiguration(detectors=detectors)
