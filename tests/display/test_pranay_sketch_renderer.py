"""Validate the segmented Pranay sketch renderer paints dancing sprite pieces."""

from __future__ import annotations

import time

import pygame

from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.pranay_sketch import PranaySketchRenderer
from heart.runtime.display_context import DisplayContext


class TestPranaySketchRenderer:
    """Exercise the segmented Pranay sketch renderer so the dancing-sprite mode stays reliable during local simulator testing."""

    def test_initialize_loads_multiple_segmented_pieces(
        self,
        device: Device,
    ) -> None:
        """Verify the renderer loads several sketch segments with source-image colors so animation can target independent pieces without flattening the artwork."""

        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        renderer = PranaySketchRenderer()

        renderer.initialize(window, PeripheralManager(), device.orientation)

        assert len(renderer.state.pieces) > 1
        assert len({piece.index for piece in renderer.state.pieces}) == len(
            renderer.state.pieces
        )
        assert any(
            pixel.r != pixel.g or pixel.g != pixel.b
            for piece in renderer.state.pieces
            for x in range(piece.image.get_width())
            for y in range(piece.image.get_height())
            if (pixel := piece.image.get_at((x, y))).a > 0
        )

    def test_real_process_draws_sketch_pixels_over_background(
        self,
        device: Device,
    ) -> None:
        """Verify the renderer paints non-background pixels after the reveal delay so the segmented sketch remains visible once the dance animation starts."""

        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        renderer = PranaySketchRenderer()
        renderer.initialize(window, PeripheralManager(), device.orientation)
        assert len(renderer.state.pieces) > 1
        renderer._start_monotonic_s = time.monotonic() - 3.0

        renderer.real_process(window, device.orientation)

        assert window.screen is not None
        background = renderer.state.background_color._as_tuple()
        changed_pixels = sum(
            1
            for x in range(window.screen.get_width())
            for y in range(window.screen.get_height())
            if window.screen.get_at((x, y))[:3] != background
        )

        assert changed_pixels > 0
