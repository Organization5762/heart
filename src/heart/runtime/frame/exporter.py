from __future__ import annotations

from collections.abc import Callable

import pygame
from PIL import Image

from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.utilities.env import Configuration, FrameExportStrategy


class FrameExporter:
    """Convert pygame surfaces into PIL images using configurable strategies."""

    def __init__(
        self,
        strategy_provider: Callable[[], FrameExportStrategy] | None = None,
    ) -> None:
        self._strategy_provider = (
            strategy_provider or Configuration.frame_export_strategy
        )

    def export(self, surface: pygame.Surface) -> Image.Image:
        strategy = self._strategy_provider()
        if strategy == FrameExportStrategy.ARRAY:
            return self._export_array(surface)
        return self._export_buffer(surface)

    def _export_buffer(self, surface: pygame.Surface) -> Image.Image:
        image_bytes = pygame.image.tostring(surface, RGBA_IMAGE_FORMAT)
        return Image.frombuffer(
            RGBA_IMAGE_FORMAT,
            surface.get_size(),
            image_bytes,
            "raw",
            RGBA_IMAGE_FORMAT,
            0,
            1,
        )

    def _export_array(self, surface: pygame.Surface) -> Image.Image:
        array = pygame.surfarray.array3d(surface)
        return Image.fromarray(array.swapaxes(0, 1))
