"""Validate WaterCube provider startup and accelerometer updates."""

from __future__ import annotations

from heart.device import Cube
from heart.device.local import LocalScreen
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.sensor import Acceleration
from heart.renderers.water_cube.provider import WaterCubeStateProvider


class _Clock:
    def __init__(self, delta_ms: float = 16.0, fps: float = 60.0) -> None:
        self.delta_ms = delta_ms
        self.fps = fps

    def get_fps(self) -> float:
        return self.fps

    def get_time(self) -> float:
        return self.delta_ms


class TestWaterCubeStateProvider:
    """Ensure the default playlist's water renderer initializes from a valid state."""

    def test_observable_steps_on_frame_tick_with_latest_accelerometer_update(
        self,
        monkeypatch,
    ) -> None:
        """Verify accelerometer input is sampled on frame ticks instead of advancing the simulation directly."""
        peripheral_manager = PeripheralManager()
        accelerometer_controller = peripheral_manager.input_io.accelerometer
        accelerometer_debug_profile = peripheral_manager.input_io.debug_accelerometer
        monkeypatch.setattr(
            accelerometer_debug_profile,
            "should_use_debug_input",
            lambda: False,
        )
        provider = WaterCubeStateProvider(
            device=LocalScreen(width=64, height=64, orientation=Cube.sides()),
        )
        observed_states = []

        provider.observable(peripheral_manager).subscribe(observed_states.append)
        accelerometer_controller.node().on_next(Acceleration(x=1.0, y=2.0, z=3.0))
        accelerometer_controller.node().on_next(Acceleration(x=4.0, y=5.0, z=6.0))

        assert len(observed_states) == 1

        peripheral_manager.input_io.frame_ticks.advance(_Clock())

        assert len(observed_states) == 2
        assert observed_states[0].gvec is None
        assert observed_states[1].gvec == Acceleration(x=4.0, y=5.0, z=6.0)
