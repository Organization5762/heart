from dataclasses import dataclass

import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class RenderColorState:
    color: Color


class RenderColor(AtomicBaseRenderer[RenderColorState]):
    def __init__(self, color: Color) -> None:
        self._initial_color = color
        super().__init__()

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        image = pygame.Surface(window.get_size())
        image.fill(self.state.color._as_tuple())
        window.blit(image, (0, 0))

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> RenderColorState:
        return RenderColorState(color=self._initial_color)

    @property
    def color(self) -> Color:
        return self.state.color