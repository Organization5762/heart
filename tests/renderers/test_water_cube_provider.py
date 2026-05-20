"""Validate WaterCube provider startup and accelerometer updates."""

from __future__ import annotations

import numpy as np
import pygame

from heart.device import Cube
from heart.device.local import LocalScreen
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.sensor import Acceleration
from heart.renderers.water_cube.provider import (HUE_STEP_DEGREES,
                                                 MAX_ACCELERATION_AVERAGE,
                                                 WaterCubeStateProvider)
from heart.renderers.water_cube.renderer import WaterCube
from heart.renderers.water_cube.state import (DEFAULT_WATER_HUE_DEGREES,
                                              WaterCubeState)
from heart.runtime.display_context import DisplayContext


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

    def test_observable_steps_at_most_once_per_100ms_with_averaged_acceleration(
        self,
        monkeypatch,
    ) -> None:
        """Verify accelerometer input is sampled on throttled frame ticks."""
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

        peripheral_manager.input_io.frame_ticks.advance(_Clock(delta_ms=16.0))

        assert len(observed_states) == 1

        accelerometer_controller.node().on_next(Acceleration(x=10.0, y=20.0, z=30.0))
        peripheral_manager.input_io.frame_ticks.advance(_Clock(delta_ms=83.0))

        assert len(observed_states) == 1

        accelerometer_controller.node().on_next(Acceleration(x=16.0, y=32.0, z=48.0))
        peripheral_manager.input_io.frame_ticks.advance(_Clock(delta_ms=1.0))

        assert len(observed_states) == 2
        assert observed_states[0].gvec is None
        assert observed_states[1].gvec == Acceleration(x=10.0, y=19.0, z=28.0)

        peripheral_manager.input_io.frame_ticks.advance(_Clock(delta_ms=99.0))

        assert len(observed_states) == 2

    def test_controller_triggers_adjust_acceleration_averaging(
        self,
        monkeypatch,
    ) -> None:
        """Verify trigger pressure tunes how aggressively water follows accelerometer changes."""
        peripheral_manager = PeripheralManager()
        monkeypatch.setattr(
            peripheral_manager.input_io.debug_accelerometer,
            "should_use_debug_input",
            lambda: False,
        )
        provider = WaterCubeStateProvider(
            device=LocalScreen(width=64, height=64, orientation=Cube.sides()),
        )
        observed_states = []
        snapshots = iter(
            [
                _gamepad_snapshot(axes={GamepadAxis.TRIGGER_LEFT: 1.0}),
                _gamepad_snapshot(axes={GamepadAxis.TRIGGER_LEFT: 1.0}),
            ]
        )
        monkeypatch.setattr(
            peripheral_manager.input_io.gamepad,
            "sample",
            lambda: next(snapshots),
        )

        provider.observable(peripheral_manager).subscribe(observed_states.append)
        peripheral_manager.input_io.accelerometer.node().on_next(
            Acceleration(x=10.0, y=0.0, z=1.0)
        )
        peripheral_manager.input_io.frame_ticks.advance(_Clock(delta_ms=100.0))
        first_average = observed_states[-1].acceleration_average
        peripheral_manager.input_io.accelerometer.node().on_next(
            Acceleration(x=20.0, y=0.0, z=1.0)
        )
        peripheral_manager.input_io.frame_ticks.advance(_Clock(delta_ms=100.0))

        assert first_average < observed_states[0].acceleration_average
        assert observed_states[-1].acceleration_average < first_average
        assert observed_states[-1].gvec.x < 20.0

    def test_held_trigger_keeps_scaling_acceleration_averaging(
        self,
        monkeypatch,
    ) -> None:
        """Verify held trigger input continues tuning viscosity on each physics tick."""
        peripheral_manager = PeripheralManager()
        monkeypatch.setattr(
            peripheral_manager.input_io.debug_accelerometer,
            "should_use_debug_input",
            lambda: False,
        )
        provider = WaterCubeStateProvider(
            device=LocalScreen(width=64, height=64, orientation=Cube.sides()),
        )
        observed_states = []
        monkeypatch.setattr(
            peripheral_manager.input_io.gamepad,
            "sample",
            lambda: _gamepad_snapshot(axes={GamepadAxis.TRIGGER_RIGHT: 1.0}),
        )

        provider.observable(peripheral_manager).subscribe(observed_states.append)
        peripheral_manager.input_io.accelerometer.node().on_next(
            Acceleration(x=1.0, y=0.0, z=1.0)
        )
        for _ in range(4):
            peripheral_manager.input_io.frame_ticks.advance(_Clock(delta_ms=100.0))

        assert observed_states[-1].acceleration_average == MAX_ACCELERATION_AVERAGE

    def test_controller_bumpers_adjust_water_hue(
        self,
        monkeypatch,
    ) -> None:
        """Verify held shoulders rotate the water color hue."""
        peripheral_manager = PeripheralManager()
        monkeypatch.setattr(
            peripheral_manager.input_io.debug_accelerometer,
            "should_use_debug_input",
            lambda: False,
        )
        provider = WaterCubeStateProvider(
            device=LocalScreen(width=64, height=64, orientation=Cube.sides()),
        )
        observed_states = []
        monkeypatch.setattr(
            peripheral_manager.input_io.gamepad,
            "sample",
            lambda: _gamepad_snapshot(buttons={GamepadButton.ZR: True}),
        )

        provider.observable(peripheral_manager).subscribe(observed_states.append)
        peripheral_manager.input_io.accelerometer.node().on_next(
            Acceleration(x=0.0, y=0.0, z=1.0)
        )
        peripheral_manager.input_io.frame_ticks.advance(_Clock(delta_ms=100.0))

        assert observed_states[-1].water_hue_degrees == (
            DEFAULT_WATER_HUE_DEGREES + HUE_STEP_DEGREES
        )
        assert not (
            observed_states[-1].water_rgb() == observed_states[0].water_rgb()
        ).all()

    def test_renderer_uses_state_water_hue(self) -> None:
        """Verify controller-selected hue reaches rendered water pixels."""
        orientation = Cube.sides()
        device = LocalScreen(width=64, height=64, orientation=orientation)
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        face_px = 64
        renderer = WaterCube(
            state=WaterCubeState(
                face_px=face_px,
                heights=np.full((face_px, face_px), face_px, dtype=np.float32),
                velocities=np.zeros((face_px, face_px), dtype=np.float32),
                gvec=Acceleration(x=0.0, y=0.0, z=1.0),
                water_hue_degrees=0.0,
            )
        )

        renderer.real_process(window, orientation)

        assert window.screen.get_at((0, 63))[:3] == (255, 0, 0)


def _gamepad_snapshot(
    *,
    axes: dict[GamepadAxis, float] | None = None,
    buttons: dict[GamepadButton, bool] | None = None,
) -> GamepadSnapshot:
    return GamepadSnapshot(
        connected=True,
        identifier="test-pad",
        axes=axes or {},
        buttons=buttons or {},
    )
