from __future__ import annotations

import pygame

from heart.device import Cube
from heart.device.local import LocalScreen
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, GamepadSnapshotEvent)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.bird_flock import BirdFlockRenderer
from heart.renderers.bird_flock.renderer import _bird_color, _controlled_hue
from heart.renderers.bird_flock.state import Bird, BirdFlockState
from heart.runtime.display_context import DisplayContext


def test_bird_flock_advances_and_stays_inside_vertical_bounds() -> None:
    birds = (
        Bird(x=250.0, y=7.0, vx=30.0, vy=-15.0, phase=0.0),
        Bird(x=10.0, y=56.0, vx=28.0, vy=14.0, phase=1.0),
    )

    result = BirdFlockRenderer._advance_birds(
        birds=birds,
        width=256,
        height=64,
        dt=0.5,
    )

    assert len(result) == len(birds)
    assert result[0].x != birds[0].x
    assert all(5 <= bird.y <= 58 for bird in result)


def test_bird_flock_render_draws_visible_flock(device) -> None:
    orientation = Cube.sides()
    surface = pygame.Surface((256, 64), pygame.SRCALPHA)
    window = DisplayContext(
        device=device,
        screen=surface,
        clock=None,
        can_configure_display=False,
    )
    renderer = BirdFlockRenderer(seed=1)
    renderer.initialize(window, PeripheralManager(), orientation)

    renderer.real_process(window, orientation)

    bright_pixels = sum(
        1
        for x in range(surface.get_width())
        for y in range(surface.get_height())
        if max(surface.get_at((x, y))[:3]) > 150
    )
    assert bright_pixels > 20


def test_bird_flock_initializes_for_local_screen() -> None:
    orientation = Cube.sides()
    device = LocalScreen(width=64, height=64, orientation=orientation)
    surface = pygame.Surface(device.full_display_size(), pygame.SRCALPHA)
    window = DisplayContext(device=device, screen=surface, clock=None)
    renderer = BirdFlockRenderer(seed=2)

    renderer.initialize(window, PeripheralManager(), orientation)

    assert len(renderer.state.birds) == 24
    assert all(0 <= bird.x <= 256 for bird in renderer.state.birds)


def test_bumpers_control_bird_count(monkeypatch, device) -> None:
    orientation = Cube.sides()
    surface = pygame.Surface((256, 64), pygame.SRCALPHA)
    window = DisplayContext(
        device=device,
        screen=surface,
        clock=None,
        can_configure_display=False,
    )
    manager = PeripheralManager()
    renderer = BirdFlockRenderer(seed=3)
    renderer.initialize(window, manager, orientation)
    renderer.set_state(
        BirdFlockState(
            birds=renderer.state.birds[:10],
            last_time_s=renderer.state.last_time_s - 0.01,
        )
    )
    monkeypatch.setattr(
        manager.input_io.controls,
        "gamepads",
        lambda **_kwargs: (
            GamepadSnapshotEvent(
                joystick_id=0,
                snapshot=_gamepad_snapshot(buttons={GamepadButton.ZR: True}),
            ),
        ),
    )

    renderer.real_process(window, orientation)

    assert len(renderer.state.birds) == 11


def test_left_and_right_triggers_control_bird_color_hue() -> None:
    idle = _gamepad_snapshot()
    right = _gamepad_snapshot(axes={GamepadAxis.TRIGGER_RIGHT: 1.0})
    left = _gamepad_snapshot(axes={GamepadAxis.TRIGGER_LEFT: 1.0})

    assert _controlled_hue(hue_degrees=90.0, gamepad=idle, dt=1.0) == 90.0
    assert _controlled_hue(hue_degrees=90.0, gamepad=right, dt=1.0) > 90.0
    assert _controlled_hue(hue_degrees=180.0, gamepad=left, dt=1.0) < 180.0
    assert _bird_color(90.0) != _bird_color(180.0)


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
