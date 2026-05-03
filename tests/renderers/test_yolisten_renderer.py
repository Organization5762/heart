"""Validate YoListenRenderer rendering against DisplayContext surfaces."""

from __future__ import annotations

import pygame
from reactivex.subject import BehaviorSubject

from heart.device import Device, Rectangle
from heart.peripheral.core.input import FrameTick
from heart.peripheral.switch import SwitchState
from heart.renderers.yolisten.renderer import YoListenRenderer
from heart.runtime.display_context import DisplayContext


class _StubPeripheralManager:
    class _StubFrameTickController:
        def __init__(self) -> None:
            self._stream = BehaviorSubject(
                FrameTick(
                    frame_index=0,
                    delta_ms=0.0,
                    delta_s=0.0,
                    monotonic_s=0.0,
                    fps=None,
                )
            )

        def observable(self):
            return self._stream

    def __init__(self, window: DisplayContext) -> None:
        self.window = BehaviorSubject(window)
        self.frame_tick_controller = self._StubFrameTickController()
        self._switch = BehaviorSubject(SwitchState(0, 0, 0, 0, 0))

    def get_main_switch_subscription(self):
        return self._switch


class TestYoListenRenderer:
    """Ensure YoListenRenderer works with DisplayContext so text rendering survives the wrapped display API."""

    def test_real_process_uses_display_context_surface(
        self,
        device: Device,
    ) -> None:
        """Verify YoListenRenderer renders through `DisplayContext.screen` so runtime rendering does not crash on surface-only APIs."""
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size(), pygame.SRCALPHA),
            clock=pygame.time.Clock(),
        )
        renderer = YoListenRenderer()
        peripheral_manager = _StubPeripheralManager(window)
        orientation = Rectangle.with_layout(4, 1)

        renderer.initialize(window, peripheral_manager, orientation)
        renderer.real_process(window, orientation)

        assert window.screen is not None
