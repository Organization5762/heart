import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.renderers import StatefulBaseRenderer
from heart.renderers.color.state import RenderColorState
from heart.runtime.display_context import DisplayContext


class RenderColor(StatefulBaseRenderer[RenderColorState]):
    def __init__(
        self,
        color: Color | None = None,
        state: RenderColorState | None = None,
    ) -> None:
        if state is None:
            if color is None:
                raise ValueError("RenderColor requires a color or state")
            state = RenderColorState(color=color)
        super().__init__(state=state)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        image = pygame.Surface(window.get_size())
        image.fill(self.state.color._as_tuple())
        window.blit(image, (0, 0))

    @property
    def color(self) -> Color:
        return self.state.color
