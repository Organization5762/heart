import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.pixels.provider import (BorderStateProvider,
                                             RainStateProvider,
                                             SlinkyStateProvider)
from heart.renderers.pixels.state import BorderState, RainState, SlinkyState


class Border(StatefulBaseRenderer[BorderState]):
    def __init__(
        self,
        width: int,
        color: Color | None = None,
        provider: BorderStateProvider | None = None,
    ) -> None:
        self._provider = provider or BorderStateProvider(color)
        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.FULL
        self.width = width

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
        self._provider.set_color(color)


class Rain(StatefulBaseRenderer[RainState]):
    def __init__(
        self,
        provider: RainStateProvider | None = None,
    ) -> None:
        self._provider: RainStateProvider | None = provider
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.l = 8
        self.starting_color = Color(r=173, g=216, b=230)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self.builder is None:
            width, height = window.get_size()
            self._provider = self._provider or RainStateProvider(
                width=width,
                height=height,
                peripheral_manager=peripheral_manager,
            )
            self.builder = self._provider
        super().initialize(window, clock, peripheral_manager, orientation)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        new_y = self.state.current_y
        starting_point = self.state.starting_point

        for i in range(self.l):
            color = self.starting_color.dim(fraction=i / self.l)
            window.set_at((starting_point, new_y - i), color)


class Slinky(StatefulBaseRenderer[SlinkyState]):
    def __init__(self, provider: SlinkyStateProvider | None = None) -> None:
        self._provider: SlinkyStateProvider | None = provider
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.l = 10
        self.starting_color = Color(r=255, g=165, b=0)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self.builder is None:
            width, height = window.get_size()
            self._provider = self._provider or SlinkyStateProvider(
                width=width,
                height=height,
                peripheral_manager=peripheral_manager,
            )
            self.builder = self._provider
        super().initialize(window, clock, peripheral_manager, orientation)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        new_y = self.state.current_y
        starting_point = self.state.starting_point

        window.set_at((starting_point, new_y), self.starting_color)
        dimmed_color = self.starting_color.dim(fraction=1 / self.l)
        window.set_at((starting_point + 1, new_y), dimmed_color)
        window.set_at((starting_point - 1, new_y), dimmed_color)
        for i in range(self.l):
            final_color = self.starting_color.dim(fraction=i / self.l)
            window.set_at((starting_point, new_y + i), final_color)
            window.set_at((starting_point, new_y - i), final_color)
            if i < 3:
                more_dim = self.starting_color.dim(fraction=(i + 1) / self.l)
                window.set_at((starting_point + 1, new_y + i), more_dim)
                window.set_at((starting_point - 1, new_y - i), more_dim)
