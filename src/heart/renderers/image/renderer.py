import pygame

from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.image.provider import RenderImageStateProvider
from heart.renderers.image.state import RenderImageState
from heart.runtime.display_context import DisplayContext


class RenderImage(StatefulBaseRenderer[RenderImageState]):
    """Render an image sourced from an asset file or a renderer event stream."""

    def __init__(
        self,
        image_file: str | None = None,
        provider: RenderImageStateProvider | None = None,
    ) -> None:
        if provider is None:
            if image_file is None:
                raise ValueError("RenderImage requires an image_file or provider")
            provider = RenderImageStateProvider(image_file=image_file)
        self._provider = provider
        super().__init__(builder=self._provider)
        self._scaled_image: pygame.Surface | None = None
        self._scaled_size: tuple[int, int] | None = None

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if self._scaled_image is None or self._scaled_size != self.state.window_size:
            self._scaled_image = pygame.transform.scale(
                self.state.base_image, self.state.window_size
            )
            self._scaled_size = self.state.window_size
        window.blit(self._scaled_image, (0, 0))


class ContainRenderImage(RenderImage):
    """Render an image using contain/letterbox scaling."""

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        base_width, base_height = self.state.base_image.get_size()
        target_width, target_height = window.get_size()
        if (
            base_width <= 0
            or base_height <= 0
            or target_width <= 0
            or target_height <= 0
        ):
            return

        scale = min(target_width / base_width, target_height / base_height)
        scaled_size = (
            max(1, round(base_width * scale)),
            max(1, round(base_height * scale)),
        )
        if self._scaled_image is None or self._scaled_size != scaled_size:
            self._scaled_image = pygame.transform.smoothscale(
                self.state.base_image, scaled_size
            )
            self._scaled_size = scaled_size

        offset = (
            (target_width - scaled_size[0]) // 2,
            (target_height - scaled_size[1]) // 2,
        )
        window.fill((0, 0, 0))
        window.blit(self._scaled_image, offset)
