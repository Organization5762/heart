"""Validate YoListenRenderer rendering against DisplayContext surfaces."""

from __future__ import annotations

import pygame
from manyfold.architecture import NewValues

from heart.device import Device, Rectangle
from heart.peripheral.core.input.io import SwitchStateEvent
from heart.peripheral.core.manager import PeripheralManager
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
        switch_stream: NewValues[SwitchStateEvent] = NewValues()
        monkeypatch.setattr(
            peripheral_manager.input_io,
            "main_switch_stream",
            lambda: switch_stream,
        )
        peripheral_manager.window.on_next(window)
        orientation = Rectangle.with_layout(4, 1)

        renderer.initialize(window, peripheral_manager, orientation)
        renderer.real_process(window, orientation)

        assert window.screen is not None
