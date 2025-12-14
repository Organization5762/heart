import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.renderers import StatefulBaseRenderer
from heart.renderers.color.provider import RenderColorStateProvider
from heart.renderers.color.state import RenderColorState


class RenderColor(StatefulBaseRenderer[RenderColorState]):
    def __init__(self, color: Color) -> None:
        super().__init__(builder=RenderColorStateProvider(color))

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        image = pygame.Surface(window.get_size())
        image.fill(self.state.color._as_tuple())
        window.blit(image, (0, 0))

    @property
    def color(self) -> Color:
        return self.state.color
