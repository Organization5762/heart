"""Validate Mandelbrot title preview initialization."""

from __future__ import annotations

from unittest.mock import Mock

import pygame

from heart import DeviceDisplayMode
from heart.renderers.mandelbrot.title import MandelbrotTitle
from heart.runtime.display_context import DisplayContext


class _StubMandelbrotMode:
    instances: list["_StubMandelbrotMode"] = []

    def __init__(self) -> None:
        self.initialize = Mock()
        self._internal_process = Mock(side_effect=self._draw_preview)
        self.reset = Mock()
        type(self).instances.append(self)

    def _draw_preview(self, window, peripheral_manager, orientation) -> None:
        del peripheral_manager, orientation
        assert window.screen is not None
        window.screen.fill((12, 34, 56))


class TestMandelbrotTitle:
    """Ensure Mandelbrot title previews use the real scene geometry."""

    def test_initialize_uses_full_display_and_passes_runtime_orientation(
        self,
        device,
        manager,
        monkeypatch,
    ) -> None:
        """Verify the title preview uses the same orientation and full-size canvas as the real Mandelbrot mode."""

        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbrot.title.MandelbrotMode",
            _StubMandelbrotMode,
        )
        title = MandelbrotTitle()

        title.initialize(window, manager, device.orientation)

        assert title.device_display_mode == DeviceDisplayMode.FULL
        stub = _StubMandelbrotMode.instances[-1]
        stub.initialize.assert_called_once_with(window, manager, device.orientation)
        stub._internal_process.assert_called_once_with(
            window,
            manager,
            device.orientation,
        )
        stub.reset.assert_called_once_with()
        assert title.state.image.get_size() == device.full_display_size()
        assert title.state.image.get_at((0, 0))[:3] == (12, 34, 56)
