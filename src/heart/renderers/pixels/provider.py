import random
from dataclasses import replace

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

    def update_color(self, state: BorderState, color: Color) -> BorderState:
        return replace(state, color=color)


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

    def next_state(self, state: RainState, width: int, height: int) -> RainState:
        new_y = state.current_y + 1
        if new_y > height:
            return replace(
                state,
                starting_point=random.randint(0, width),
            )
        return replace(state, current_y=new_y)


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

    def next_state(self, state: SlinkyState, width: int, height: int) -> SlinkyState:
        new_y = state.current_y + 1
        if new_y > height:
            return replace(
                state,
                starting_point=random.randint(0, width),
            )
        return replace(state, current_y=new_y)
