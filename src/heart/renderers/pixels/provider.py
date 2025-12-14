import random

import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.pixels.state import BorderState, RainState, SlinkyState


class BorderStateProvider:
    def __init__(self, initial_color: Color | None = None) -> None:
        self._initial_color = initial_color or Color.random()

    def create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> BorderState:
        return BorderState(color=self._initial_color)


class RainStateProvider:
    def create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> RainState:
        initial_y = random.randint(0, 20)
        return RainState(
            random.randint(0, window.get_width()),
            current_y=initial_y,
        )


class SlinkyStateProvider:
    def create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> SlinkyState:
        return SlinkyState(
            starting_point=random.randint(0, window.get_size()[0]),
            current_y=random.randint(0, 20),
        )
