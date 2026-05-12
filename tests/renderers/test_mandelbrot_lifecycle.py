"""Validate Mandelbrot renderer lifecycle cleanup."""

from __future__ import annotations

from unittest.mock import Mock

import pygame

from heart.device import Rectangle
from heart.device.local import LocalScreen
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.mandelbrot.control_mappings import KeyboardControls
from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.runtime.display_context import DisplayContext


class _Subscription:
    def __init__(self) -> None:
        self.dispose_calls = 0

    def dispose(self) -> None:
        self.dispose_calls += 1


class _Stream:
    def __init__(self) -> None:
        self.subscriptions: list[_Subscription] = []

    def subscribe(self, **_kwargs) -> _Subscription:
        subscription = _Subscription()
        self.subscriptions.append(subscription)
        return subscription


class _MandelbrotProfile:
    def __init__(self) -> None:
        self.motion_state = _Stream()
        self.command_events = _Stream()


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

    def test_keyboard_controls_disposes_profile_subscriptions(self) -> None:
        """Verify Mandelbrot input stream subscriptions are owned and released by the control adapter."""
        profile = _MandelbrotProfile()

        controls = KeyboardControls(scene_controls=Mock(), profile=profile)
        controls.dispose()

        assert profile.motion_state.subscriptions[0].dispose_calls == 1
        assert profile.command_events.subscriptions[0].dispose_calls == 1

    def test_reset_disposes_keyboard_controls(self) -> None:
        """Verify renderer reset releases Mandelbrot controls before the next scene entry."""
        renderer = MandelbrotMode()
        keyboard_controls = Mock()
        renderer.keyboard_controls = keyboard_controls
        renderer.scene_controls = Mock()
        renderer.input_error = True

        renderer.reset()

        keyboard_controls.dispose.assert_called_once_with()
        assert renderer.keyboard_controls is None
        assert renderer.scene_controls is None
        assert renderer.input_error is False

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
