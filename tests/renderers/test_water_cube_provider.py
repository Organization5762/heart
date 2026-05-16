"""Validate WaterCube provider startup and accelerometer updates."""

from __future__ import annotations

from heart.device import Cube
from heart.device.local import LocalScreen
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.sensor import Acceleration
from heart.renderers.water_cube.provider import WaterCubeStateProvider


class TestWaterCubeStateProvider:
    """Ensure the default playlist's water renderer initializes from a valid state."""

    def test_observable_emits_initial_state_before_accelerometer_updates(
        self,
        monkeypatch,
    ) -> None:
        """Verify startup emits a WaterCubeState instead of feeding the initial state through the reducer as acceleration."""
        peripheral_manager = PeripheralManager()
        accelerometer_controller = peripheral_manager.accelerometer_controller
        accelerometer_debug_profile = peripheral_manager.accelerometer_debug_profile
        monkeypatch.setattr(
            accelerometer_debug_profile,
            "should_use_debug_input",
            lambda: False,
        )
        provider = WaterCubeStateProvider(
            accelerometer_controller=accelerometer_controller,
            accelerometer_debug_profile=accelerometer_debug_profile,
            device=LocalScreen(width=64, height=64, orientation=Cube.sides()),
        )
        observed_states = []

        provider.observable(peripheral_manager).subscribe(observed_states.append)
        accelerometer_controller.node().on_next(Acceleration(x=1.0, y=2.0, z=3.0))

        assert len(observed_states) == 2
        assert observed_states[0].gvec is None
        assert observed_states[1].gvec == Acceleration(x=1.0, y=2.0, z=3.0)
