"""Validate externally controlled sensor hooks so Beats can drive runtime-owned input values."""

from __future__ import annotations

from heart.peripheral.core.input.debug import InputDebugTap
from heart.peripheral.core.input.external_sensors import ExternalSensorHub
from heart.peripheral.sensor import Acceleration


class TestExternalSensorHub:
    """Ensure externally controlled sensors publish snapshots and accelerometer vectors so websocket-driven input remains observable and usable."""

    def test_set_value_publishes_peripheral_snapshot(self) -> None:
        """Verify scalar sensor updates publish structured snapshots so Beats can rediscover controlled values from the runtime stream."""
        debug_tap = InputDebugTap()
        hub = ExternalSensorHub(debug_tap)

        hub.set_value("totem.sensor:payload.level", 0.75)

        snapshot = debug_tap.snapshot()
        assert snapshot[-1].source_id == "totem.sensor"
        assert snapshot[-1].stream_name == "beats.sensor.control"
        assert snapshot[-1].payload == {"payload": {"level": 0.75}}

    def test_accelerometer_updates_emit_runtime_vector(self) -> None:
        """Verify accelerometer-axis updates resolve into an Acceleration value so existing renderer providers can consume websocket-driven motion hooks."""
        hub = ExternalSensorHub(InputDebugTap())
        observed: list[Acceleration | None] = []
        hub.observable_acceleration().subscribe(observed.append)

        hub.set_value("accelerometer:debug:x", 1.0)
        hub.set_value("accelerometer:debug:z", 12.5)
        hub.clear_value("accelerometer:debug:x")
        hub.clear_value("accelerometer:debug:z")

        assert observed == [
            None,
            Acceleration(x=1.0, y=0.0, z=0.0),
            Acceleration(x=1.0, y=0.0, z=12.5),
            Acceleration(x=0.0, y=0.0, z=12.5),
            None,
        ]
