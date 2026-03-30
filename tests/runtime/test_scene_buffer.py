"""Validate scene-like drawing helpers used by CPU renderers."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pygame

from heart.runtime.display_context import DisplayContext
from heart.runtime.scene_buffer import PygameSceneCanvas, build_scene_canvas


class TestDisplayContextSceneApi:
    """Ensure DisplayContext exposes scene-like helpers so renderers can migrate off raw pygame calls."""

    def test_blit_array_writes_rgb_pixels(self, device) -> None:
        """Verify blit_array applies a surfarray-compatible RGB payload to the backing screen. This matters because renderers need a stable CPU composition API before pygame becomes only the final presentation step."""

        context = DisplayContext(device=device)
        context.initialize()

        pixel_array = np.zeros((context.get_width(), context.get_height(), 3), dtype=np.uint8)
        pixel_array[1, 2] = np.array([255, 64, 32], dtype=np.uint8)

        context.blit_array(pixel_array)

        assert context.screen is not None
        assert context.screen.get_at((1, 2))[:3] == (255, 64, 32)

    def test_blits_copies_multiple_surfaces(self, device) -> None:
        """Verify blits forwards batched copy operations to the backing screen. This matters because scene composition should keep pygame batch-blit semantics while the renderer API migrates."""

        context = DisplayContext(device=device)
        context.initialize()

        source_a = pygame.Surface((2, 2), pygame.SRCALPHA)
        source_b = pygame.Surface((2, 2), pygame.SRCALPHA)
        source_a.fill((255, 0, 0, 255))
        source_b.fill((0, 255, 0, 255))

        context.blits(
            [
                (source_a, (0, 0), None, 0),
                (source_b, (3, 1), None, 0),
            ]
        )

        assert context.screen is not None
        assert context.screen.get_at((0, 0))[:3] == (255, 0, 0)
        assert context.screen.get_at((3, 1))[:3] == (0, 255, 0)


class TestSceneCanvasFallback:
    """Ensure the Python scene canvas fallback keeps the migration path usable without the native wheel."""

    def test_build_scene_canvas_falls_back_to_pygame(self) -> None:
        """Verify build_scene_canvas returns a pygame-backed adapter when heart_rust is unavailable. This matters because native adoption needs to stay optional while renderer call sites migrate."""

        with patch("heart.runtime.scene_buffer.optional_import", return_value=None):
            canvas = build_scene_canvas((4, 3))

        assert isinstance(canvas, PygameSceneCanvas)
        assert canvas.get_size() == (4, 3)

    def test_pygame_scene_canvas_accepts_rgba_arrays(self) -> None:
        """Verify the pygame-backed adapter can blit RGBA arrays through the shared scene API. This matters because existing CPU renderers often compose arrays before presenting them."""

        canvas = PygameSceneCanvas(pygame.Surface((4, 4), pygame.SRCALPHA))
        pixel_array = np.zeros((2, 2, 4), dtype=np.uint8)
        pixel_array[0, 0] = np.array([12, 34, 56, 255], dtype=np.uint8)

        canvas.blit_array(pixel_array, dest=(1, 1))

        assert canvas.surface.get_at((1, 1)) == pygame.Color(12, 34, 56, 255)
