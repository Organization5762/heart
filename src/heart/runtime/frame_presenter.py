from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pygame
from PIL import Image

from heart.device import Device
from heart.runtime.display_context import DisplayContext
from heart.runtime.render_pipeline import RenderPipeline

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


@dataclass
class FramePresenter:
    device: Device
    display: DisplayContext
    render_pipeline: RenderPipeline

    def present(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        render_surface: pygame.Surface | None,
    ) -> None:
        if not renderers:
            return
        pygame.display.flip()
        if render_surface is not None:
            self._present_render_surface(render_surface)
            return
        self._present_from_screen()

    def _present_render_surface(self, render_surface: pygame.Surface) -> None:
        render_image = self.render_pipeline.finalize_rendering(render_surface)
        device_image = (
            render_image.convert("RGB") if render_image.mode != "RGB" else render_image
        )
        self.device.set_image(device_image)

    def _present_from_screen(self) -> None:
        if self.display.screen is None:
            raise RuntimeError("GameLoop screen is not initialized")
        screen_array = pygame.surfarray.array3d(self.display.screen)
        transposed_array = np.transpose(screen_array, (1, 0, 2))
        pil_image = Image.fromarray(transposed_array)
        self.device.set_image(pil_image)
