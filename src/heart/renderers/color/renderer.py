import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers import StatefulBaseRenderer
from heart.renderers.color.state import RenderColorState


class RenderColor(StatefulBaseRenderer[RenderColorState]):
    def __init__(
        self,
        color: Color | None = None,
        state: RenderColorState | None = None,
        provider: ObservableProvider[RenderColorState] | None = None,
    ) -> None:
        if provider is not None and (color is not None or state is not None):
            raise ValueError(
                "RenderColor accepts either a provider or a color/state snapshot"
            )
        if provider is None:
            if state is None:
                if color is None:
                    raise ValueError("RenderColor requires a color or provider")
                state = RenderColorState(color=color)
            super().__init__(state=state)
        else:
            self._provider = provider
            super().__init__(builder=self._provider)

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
