import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.pixels.provider import (BorderProvider,
                                                     RainProvider,
                                                     SlinkyProvider)
from heart.display.renderers.pixels.state import (BorderState, RainState,
                                                  SlinkyState)
from heart.peripheral.core.manager import PeripheralManager


class Border(AtomicBaseRenderer[BorderState]):
    def __init__(self, width: int, color: Color | None = None) -> None:
        self.width = width
        self.provider = BorderProvider(color or Color.random())
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> BorderState:
        return self.provider.initial_state()

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        color_value = self.state.color._as_tuple()
        for x in range(width):
            for y in range(self.width):
                window.set_at((x, y), color_value)
                window.set_at((x, height - 1 - y), color_value)

        for y in range(height):
            for x in range(self.width):
                window.set_at((x, y), color_value)
                window.set_at((width - 1 - x, y), color_value)

    def set_color(self, color: Color) -> None:
        self.set_state(self.provider.update_color(self.state, color))


class Rain(AtomicBaseRenderer[RainState]):
    def __init__(self) -> None:
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL
        self.provider = RainProvider(length=8, starting_color=Color(r=173, g=216, b=230))

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> RainState:
        return self.provider.initial_state(window)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.provider.advance(self.state, window)
        self.set_state(state)
        starting_point = state.starting_point
        new_y = state.current_y

        for i in range(self.provider.length):
            color = self.provider.starting_color.dim(fraction=i / self.provider.length)
            window.set_at((starting_point, new_y - i), color)


class Slinky(AtomicBaseRenderer[SlinkyState]):
    def __init__(self) -> None:
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL
        self.provider = SlinkyProvider(length=10, starting_color=Color(r=255, g=165, b=0))

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> SlinkyState:
        return self.provider.initial_state(window)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.provider.advance(self.state, window)
        self.set_state(state)
        starting_point = state.starting_point
        new_y = state.current_y

        window.set_at((starting_point, new_y), self.provider.starting_color)
        faded = self.provider.starting_color.dim(fraction=1 / self.provider.length)
        window.set_at((starting_point + 1, new_y), faded)
        window.set_at((starting_point - 1, new_y), faded)

        for i in range(self.provider.length):
            final_color = self.provider.starting_color.dim(fraction=i / self.provider.length)
            window.set_at((starting_point, new_y + i), final_color)
            window.set_at((starting_point, new_y - i), final_color)
            if i < 3:
                dimmed = self.provider.starting_color.dim(
                    fraction=(i + 1) / self.provider.length
                )
                window.set_at((starting_point + 1, new_y + i), dimmed)
                window.set_at((starting_point - 1, new_y - i), dimmed)
