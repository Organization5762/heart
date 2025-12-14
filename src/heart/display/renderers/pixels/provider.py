import random

import pygame

from heart.display.color import Color
from heart.display.renderers.pixels.state import (BorderState, RainState,
                                                  SlinkyState)


class BorderProvider:
    def __init__(self, color: Color) -> None:
        self._initial_color = color

    def initial_state(self) -> BorderState:
        return BorderState(color=self._initial_color)

    def update_color(self, state: BorderState, color: Color) -> BorderState:
        return BorderState(color=color)


class RainProvider:
    def __init__(self, length: int, starting_color: Color) -> None:
        self.length = length
        self.starting_color = starting_color

    def initial_state(self, window: pygame.Surface) -> RainState:
        width = window.get_width()
        return RainState(
            starting_point=random.randint(0, max(0, width - 1)),
            current_y=random.randint(0, 20),
        )

    def advance(self, state: RainState, window: pygame.Surface) -> RainState:
        width, height = window.get_size()
        new_y = state.current_y + 1
        if new_y > height:
            return RainState(
                starting_point=random.randint(0, max(0, width - 1)),
                current_y=0,
            )
        return RainState(starting_point=state.starting_point, current_y=new_y)


class SlinkyProvider:
    def __init__(self, length: int, starting_color: Color) -> None:
        self.length = length
        self.starting_color = starting_color

    def initial_state(self, window: pygame.Surface) -> SlinkyState:
        width = window.get_width()
        return SlinkyState(
            starting_point=random.randint(0, max(0, width - 1)),
            current_y=random.randint(0, 20),
        )

    def advance(self, state: SlinkyState, window: pygame.Surface) -> SlinkyState:
        width, height = window.get_size()
        new_y = state.current_y + 1
        if new_y > height:
            return SlinkyState(
                starting_point=random.randint(0, max(0, width - 1)),
                current_y=0,
            )
        return SlinkyState(starting_point=state.starting_point, current_y=new_y)
