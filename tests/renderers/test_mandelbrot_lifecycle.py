"""Validate Mandelbrot renderer lifecycle cleanup."""

from __future__ import annotations

from unittest.mock import Mock

import pygame

from heart import DeviceDisplayMode
from heart.device import Rectangle
from heart.device.local import LocalScreen
from heart.navigation import ComposedRenderer
from heart.peripheral.core.input import GamepadButton, MandelbrotMotionState
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.mandelbrot.control_mappings import KeyboardControls
from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.renderers.mandelbrot.state import ViewMode
from heart.runtime.display_context import DisplayContext


class _Subscription:
    def __init__(self, on_next=None) -> None:
        self.on_next = on_next or (lambda _value: None)
        self.dispose_calls = 0

    def dispose(self) -> None:
        self.dispose_calls += 1


class _Stream:
    def __init__(self) -> None:
        self.subscriptions: list[_Subscription] = []

    def subscribe(self, observer=None, *, on_next=None, **_kwargs) -> _Subscription:
        callback = on_next or observer
        subscription = _Subscription(callback)
        self.subscriptions.append(subscription)
        return subscription


class _MandelbrotProfile:
    def __init__(self) -> None:
        self.motion_state = _Stream()
        self.command_events = _Stream()
        self.sampled_gamepad_state: MandelbrotMotionState | None = None
        self.sampled_gamepad_buttons: frozenset[GamepadButton] = frozenset()

    def sample_gamepad_motion_state(self) -> MandelbrotMotionState:
        return self.sampled_gamepad_state or MandelbrotMotionState()

    def sample_gamepad_buttons(self) -> frozenset[GamepadButton]:
        return self.sampled_gamepad_buttons


class _PressedKeys:
    def __init__(self, *pressed_keys: int) -> None:
        self._pressed_keys = set(pressed_keys)

    def __len__(self) -> int:
        return 512

    def __getitem__(self, key: int) -> bool:
        return key in self._pressed_keys


def _build_mandelbrot_runtime() -> tuple[
    MandelbrotMode,
    DisplayContext,
    PeripheralManager,
    Rectangle,
]:
    orientation = Rectangle.with_layout(columns=1, rows=1)
    device = LocalScreen(width=64, height=64, orientation=orientation)
    window = DisplayContext(
        device=device,
        screen=pygame.Surface(device.full_display_size()),
        clock=pygame.time.Clock(),
    )
    manager = PeripheralManager()
    renderer = MandelbrotMode()
    renderer.initialize(window, manager, orientation)
    return renderer, window, manager, orientation


class TestMandelbrotLifecycle:
    """Keep Mandelbrot entry and exit from leaking input subscriptions or reinitializing during input warmup."""

    def test_base_mandelbrot_mirrors_one_panel_across_multi_panel_rectangle(
        self,
        manager,
        monkeypatch,
    ) -> None:
        """Verify base Mandelbrot keeps mirrored content while the renderer stays in full display mode."""
        orientation = Rectangle.with_layout(columns=4, rows=1)
        device = LocalScreen(width=16, height=8, orientation=orientation)
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        renderer = MandelbrotMode()
        drawn_sizes: list[tuple[int, int]] = []

        def draw_panel(surface: pygame.Surface) -> None:
            drawn_sizes.append(surface.get_size())
            surface.fill((10 + len(drawn_sizes), 20, 30))
            pygame.draw.rect(surface, (200, 30, 40), pygame.Rect(0, 0, 8, 8))

        monkeypatch.setattr(renderer, "_draw_mandelbrot_to_surface", draw_panel)

        surface = ComposedRenderer.render_batch(
            [renderer],
            window=window,
            peripheral_manager=manager,
            orientation=orientation,
        )

        assert renderer.device_display_mode == DeviceDisplayMode.FULL
        assert renderer.state.orientation.layout.columns == 4
        assert renderer.state.orientation.layout.rows == 1
        assert drawn_sizes[-1:] == [(16, 8)]
        assert surface is not None
        assert surface.get_size() == (64, 8)
        for column in range(4):
            assert surface.get_at((column * 16, 0))[:3] == (200, 30, 40)
            assert surface.get_at((column * 16 + 15, 0))[:3] == (11, 20, 30)

    def test_full_mandelbrot_preserves_split_view_mode(
        self,
        monkeypatch,
    ) -> None:
        """Verify full Mandelbrot mode allows the shoulder-driven split view modes."""
        renderer, window, _manager, orientation = _build_mandelbrot_runtime()
        renderer.state.view_mode = ViewMode.JULIA
        draw_split = Mock()
        monkeypatch.setattr(renderer, "_draw_split_view", draw_split)
        monkeypatch.setattr(renderer, "_is_input_grace_period", lambda: True)

        renderer.real_process(window, orientation)

        assert renderer.state.view_mode == ViewMode.JULIA
        draw_split.assert_not_called()

    def test_julia_mode_renders_individual_multi_panel_rectangle_panels(
        self,
        manager,
        monkeypatch,
    ) -> None:
        """Verify Julia mode remains per-panel instead of using base Mandelbrot mirroring."""
        orientation = Rectangle.with_layout(columns=4, rows=1)
        device = LocalScreen(width=16, height=8, orientation=orientation)
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        renderer = MandelbrotMode()
        drawn_sizes: list[tuple[int, int]] = []

        def draw_panel(surface: pygame.Surface) -> None:
            drawn_sizes.append(surface.get_size())
            surface.fill((40 + len(drawn_sizes), 50, 60))

        monkeypatch.setattr(renderer, "_draw_julia_to_surface", draw_panel)
        renderer.initialize(window, manager, orientation)
        renderer.state.view_mode = ViewMode.JULIA
        renderer.real_process(window, orientation)

        assert drawn_sizes[-4:] == [(16, 8), (16, 8), (16, 8), (16, 8)]
        assert window.screen is not None
        for column in range(4):
            assert window.screen.get_at((column * 16, 0))[:3] == (
                41 + column,
                50,
                60,
            )

    def test_keyboard_controls_disposes_profile_subscriptions(self) -> None:
        """Verify Mandelbrot input stream subscriptions are owned and released by the control adapter."""
        profile = _MandelbrotProfile()

        controls = KeyboardControls(scene_controls=Mock(), profile=profile)
        controls.dispose()

        assert profile.motion_state.subscriptions[0].dispose_calls == 1
        assert profile.command_events.subscriptions[0].dispose_calls == 1

    def test_keyboard_controls_fall_back_to_current_pressed_keys(
        self,
        monkeypatch,
    ) -> None:
        """Verify Mandelbrot keyboard movement still works if stream state is stale after re-entry."""
        profile = _MandelbrotProfile()
        scene_controls = Mock()
        monkeypatch.setattr(pygame.event, "pump", lambda: None)
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: _PressedKeys(pygame.K_d))

        controls = KeyboardControls(scene_controls=scene_controls, profile=profile)
        controls.update()

        scene_controls._move.assert_called_once_with(1.0, 0.0, multiplier=1.0)

    def test_keyboard_controls_prefers_stream_motion_when_present(
        self,
        monkeypatch,
    ) -> None:
        """Verify the direct keyboard fallback does not double-apply active stream motion."""
        profile = _MandelbrotProfile()
        scene_controls = Mock()
        monkeypatch.setattr(pygame.event, "pump", lambda: None)
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: _PressedKeys(pygame.K_d))

        controls = KeyboardControls(scene_controls=scene_controls, profile=profile)
        profile.motion_state.subscriptions[0].on_next(
            MandelbrotMotionState(move_x=1.0, move_multiplier=2.0)
        )
        controls.update()

        scene_controls._move.assert_called_once_with(1.0, 0.0, multiplier=2.0)

    def test_keyboard_controls_falls_back_to_sampled_gamepad_motion(
        self,
        monkeypatch,
    ) -> None:
        """Verify connected gamepad motion still drives Mandelbrot if the stream state is idle."""
        profile = _MandelbrotProfile()
        profile.sampled_gamepad_state = MandelbrotMotionState(
            move_x=0.75,
            pan_y=-0.5,
            move_multiplier=2.0,
        )
        scene_controls = Mock()
        monkeypatch.setattr(pygame.event, "pump", lambda: None)
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: _PressedKeys())

        controls = KeyboardControls(scene_controls=scene_controls, profile=profile)
        controls.update()

        assert scene_controls._move.call_args_list == [
            ((0.75, 0.0), {"multiplier": 2.0}),
            ((0.0, -0.5), {"explicit_mode": "panning", "multiplier": 2.0}),
        ]

    def test_keyboard_controls_falls_back_to_sampled_right_shoulder_action(
        self,
        monkeypatch,
    ) -> None:
        """Verify sampled ZR presses still advance Mandelbrot when stream events are missed."""
        profile = _MandelbrotProfile()
        scene_controls = Mock()
        monkeypatch.setattr(pygame.event, "pump", lambda: None)
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: _PressedKeys())

        controls = KeyboardControls(scene_controls=scene_controls, profile=profile)
        profile.sampled_gamepad_buttons = frozenset({GamepadButton.ZR})
        controls.update()
        controls.update()

        scene_controls._increment_view_mode.assert_called_once_with()

    def test_reset_disposes_keyboard_controls(self) -> None:
        """Verify renderer reset releases Mandelbrot controls before the next scene entry."""
        renderer = MandelbrotMode()
        keyboard_controls = Mock()
        renderer.keyboard_controls = keyboard_controls
        renderer.scene_controls = Mock()
        renderer.input_error = True
        renderer.clock = Mock()
        renderer.width = 64
        renderer.height = 32
        renderer.individual_screen_width = 16
        renderer.individual_screen_height = 32
        renderer.screens[(0, 0)] = pygame.Surface((64, 32))
        renderer._split_view_surfaces[(32, 32)] = (
            pygame.Surface((32, 32)),
            pygame.Surface((32, 32)),
        )
        renderer.cached_result = object()
        renderer.last_params = object()
        renderer.cached_julia_result = object()
        renderer.last_julia_params = object()

        renderer.reset()

        keyboard_controls.dispose.assert_called_once_with()
        assert renderer.keyboard_controls is None
        assert renderer.scene_controls is None
        assert renderer.input_error is False
        assert renderer.clock is None
        assert renderer.width is None
        assert renderer.height is None
        assert renderer.individual_screen_width is None
        assert renderer.individual_screen_height is None
        assert renderer.screens == {}
        assert renderer._split_view_surfaces == {}
        assert renderer.cached_result is None
        assert renderer.last_params is None
        assert renderer.cached_julia_result is None
        assert renderer.last_julia_params is None

    def test_input_grace_period_does_not_reset_renderer(self, monkeypatch) -> None:
        """Verify the startup input grace period does not masquerade as an input-device failure."""
        renderer, window, manager, orientation = _build_mandelbrot_runtime()
        process_input = Mock(side_effect=AssertionError("input should be skipped"))
        reset = Mock(side_effect=AssertionError("reset should not be called"))
        monkeypatch.setattr(renderer, "process_input", process_input)
        monkeypatch.setattr(renderer, "reset", reset)
        monkeypatch.setattr(renderer, "_is_input_grace_period", lambda: True)
        monkeypatch.setattr(renderer, "_draw_mandelbrot_to_surface", lambda _surface: None)

        renderer.real_process(window, orientation)

        process_input.assert_not_called()
        reset.assert_not_called()
        assert renderer.input_error is False
