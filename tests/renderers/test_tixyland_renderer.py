"""Validate Tixyland controller tuning and seeded color rendering."""

from __future__ import annotations

import numpy as np
import pygame

from heart.device import Cube
from heart.device.local import LocalScreen
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.tixyland.provider import (MAX_SPEED_SCALE,
                                               TixylandStateProvider)
from heart.renderers.tixyland.renderer import Tixyland
from heart.renderers.tixyland.state import TixylandState
from heart.runtime.display_context import DisplayContext


class _Clock:
    def __init__(self, delta_ms: float = 100.0) -> None:
        self.delta_ms = delta_ms

    def get_time(self) -> float:
        return self.delta_ms

    def get_fps(self) -> float:
        return 60.0


class TestTixyland:
    def test_held_trigger_keeps_scaling_speed(self, monkeypatch) -> None:
        peripheral_manager = PeripheralManager()
        provider = TixylandStateProvider(peripheral_manager)
        observed_states: list[TixylandState] = []
        monkeypatch.setattr(
            peripheral_manager.input_io.gamepad,
            "sample",
            lambda: _gamepad_snapshot(axes={GamepadAxis.TRIGGER_RIGHT: 1.0}),
        )

        provider.observable().subscribe(observed_states.append)
        for _ in range(30):
            peripheral_manager.input_io.frame_ticks.advance(_Clock())

        assert observed_states[-1].speed_scale == MAX_SPEED_SCALE
        assert observed_states[-1].time_seconds > 3.0

    def test_bumpers_change_hue(self, monkeypatch) -> None:
        peripheral_manager = PeripheralManager()
        provider = TixylandStateProvider(peripheral_manager)
        observed_states: list[TixylandState] = []
        monkeypatch.setattr(
            peripheral_manager.input_io.gamepad,
            "sample",
            lambda: _gamepad_snapshot(buttons={GamepadButton.ZR: True}),
        )

        provider.observable().subscribe(observed_states.append)
        peripheral_manager.input_io.frame_ticks.advance(_Clock())

        assert observed_states[-1].hue_degrees > observed_states[0].hue_degrees

    def test_renderer_uses_hue_and_seeded_coordinates(self) -> None:
        orientation = Cube.sides()
        device = LocalScreen(width=64, height=64, orientation=orientation)
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        captured_x: list[np.ndarray] = []

        def fn(_t, _i, _y, x):
            captured_x.append(x)
            return np.ones(x.shape)

        renderer = Tixyland(
            fn=fn,
            state=TixylandState(hue_degrees=120.0, seed=2),
        )

        renderer.real_process(window, orientation)

        assert captured_x[0][0, 0] == 62
        assert window.screen.get_at((0, 0))[:3] == (165, 255, 165)


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
