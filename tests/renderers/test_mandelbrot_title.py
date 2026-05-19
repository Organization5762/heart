"""Validate Mandelbrot title preview initialization."""

from __future__ import annotations

from unittest.mock import Mock

import pygame

from heart import DeviceDisplayMode
from heart.device import Rectangle
from heart.navigation import ComposedRenderer
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
    """Ensure Mandelbrot title previews stay tileable in selection screens."""

    def test_initialize_uses_mirrored_display_and_single_panel_preview(
        self,
        device,
        manager,
        monkeypatch,
    ) -> None:
        """Verify the title preview renders once per panel instead of spanning the whole device."""

        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.individual_display_size()),
            clock=pygame.time.Clock(),
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbrot.title.MandelbrotMode",
            _StubMandelbrotMode,
        )
        title = MandelbrotTitle()

        title.initialize(window, manager, device.orientation)

        assert title.device_display_mode == DeviceDisplayMode.MIRRORED
        stub = _StubMandelbrotMode.instances[-1]
        preview_orientation = stub.initialize.call_args.args[2]
        assert isinstance(preview_orientation, Rectangle)
        assert preview_orientation.layout.columns == 1
        assert preview_orientation.layout.rows == 1
        stub.initialize.assert_called_once_with(window, manager, preview_orientation)
        stub._internal_process.assert_called_once_with(
            window,
            manager,
            preview_orientation,
        )
        stub.reset.assert_called_once_with()
        assert title.state.image.get_size() == device.individual_display_size()
        assert title.state.image.get_at((0, 0))[:3] == (12, 34, 56)

    def test_composed_title_output_is_tiled(
        self,
        device,
        manager,
        monkeypatch,
    ) -> None:
        """Verify composed title rendering repeats the Mandelbrot preview per physical panel."""

        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbrot.title.MandelbrotMode",
            _StubMandelbrotMode,
        )

        surface = ComposedRenderer.render_batch(
            [MandelbrotTitle()],
            window=window,
            peripheral_manager=manager,
            orientation=device.orientation,
        )

        assert surface is not None
        assert surface.get_size() == device.full_display_size()
        panel_width, panel_height = device.individual_display_size()
        for column in range(device.orientation.layout.columns):
            assert surface.get_at((column * panel_width, 0))[:3] == (12, 34, 56)
            panel_bottom_right = (
                column * panel_width + panel_width - 1,
                panel_height - 1,
            )
            assert surface.get_at(panel_bottom_right)[:3] == (12, 34, 56)
