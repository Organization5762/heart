from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pygame
from PIL import Image

from heart.device import Device
from heart.runtime.display_context import DisplayContext
from heart.runtime.frame_exporter import FrameExporter
from heart.runtime.render_pipeline import RenderPipeline

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


@dataclass
class FramePresenter:
    device: Device
    display: DisplayContext
    render_pipeline: RenderPipeline
    frame_exporter: FrameExporter = field(default_factory=FrameExporter)

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
        render_image = self.frame_exporter.export(render_surface)
        device_image = self._prepare_device_image(render_image)
        self.device.set_image(device_image)

    def _present_from_screen(self) -> None:
        if self.display.screen is None:
            raise RuntimeError("GameLoop screen is not initialized")
        screen_image = self.frame_exporter.export(self.display.screen)
        device_image = self._prepare_device_image(screen_image)
        self.device.set_image(device_image)

    @staticmethod
    def _prepare_device_image(image: Image.Image) -> Image.Image:
        if image.mode != "RGB":
            return image.convert("RGB")
        return image
