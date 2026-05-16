"""Validate YoListenRenderer rendering against DisplayContext surfaces."""

from __future__ import annotations

import pygame
from manyfold import BehaviorSubject

from heart.device import Device, Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState
from heart.renderers.yolisten.renderer import YoListenRenderer
from heart.runtime.display_context import DisplayContext


class TestYoListenRenderer:
    """Ensure YoListenRenderer works with DisplayContext so text rendering survives the wrapped display API."""

    def test_real_process_uses_display_context_surface(
        self,
        device: Device,
        monkeypatch,
    ) -> None:
        """Verify YoListenRenderer renders through `DisplayContext.screen` so runtime rendering does not crash on surface-only APIs."""
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size(), pygame.SRCALPHA),
            clock=pygame.time.Clock(),
        )
        renderer = YoListenRenderer()
        peripheral_manager = PeripheralManager()
        switch_stream = BehaviorSubject(SwitchState(0, 0, 0, 0, 0))
        monkeypatch.setattr(
            peripheral_manager,
            "get_main_switch_subscription",
            lambda: switch_stream,
        )
        peripheral_manager.window.on_next(window)
        orientation = Rectangle.with_layout(4, 1)

        renderer.initialize(window, peripheral_manager, orientation)
        renderer.real_process(window, orientation)

        assert window.screen is not None
