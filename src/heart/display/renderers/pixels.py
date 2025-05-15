import random

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


class RandomPixel(BaseRenderer):
    def __init__(
        self, num_pixels=1, color: Color | None = None, brightness: float = 1.0
    ) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.num_pixels = num_pixels
        self.color = color
        self.brightness = brightness

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()

        # TODO: We need a mask here because the most expensive thing is the random function.
        # A mask of noise would allow for cheaper sampling of randomness
        pixels = [
            (random.randint(0, width - 1), random.randint(0, height - 1))
            for _ in range(self.num_pixels)
        ]
        random_color = self.color or Color.random()
        color_value = [int(x * self.brightness) for x in random_color._as_tuple()]
        for x, y in pixels:
            window.set_at((x, y), color_value)


class Border(BaseRenderer):
    def __init__(self, width: int, color: Color | None = None) -> None:
        # TODO: This whole freaking this is broken
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.width = width
        self.color = color or Color.random()

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()

        # Draw the border
        color_value = self.color._as_tuple()
        for x in range(width):
            # Top and Bottom
            for y in range(self.width):
                window.set_at((x, y), color_value)
                window.set_at((x, height - 1 - y), color_value)

        for y in range(height):
            # Left and Right
            for x in range(self.width):
                window.set_at((x, y), color_value)
                window.set_at((width - 1 - x, y), color_value)


class Rain(BaseRenderer):
    def __init__(self) -> None:
        # TODO: This whole freaking this is broken
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.l = 8
        self.starting_color = Color(r=173, g=216, b=230)

    def _change_starting_point(self, width):
        self.starting_point = random.randint(0, width)
        self.current_y = 0

    def initialize(self, window: pygame.Surface, clock: pygame.time.Clock, peripheral_manager: PeripheralManager, orientation: Orientation,):
        self._change_starting_point(width=window.get_width())
        self.current_y = random.randint(0, 20)
        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()

        # Move one unit
        self.current_y += 1

        # Now draw a rain drop
        # It should decrease the saturation, but also dim

        for i in range(self.l):
            color = self.starting_color.dim(fraction=i / self.l)
            window.set_at((self.starting_point, self.current_y - i), color)

        if self.current_y > height:
            self._change_starting_point(width=width)


class Slinky(BaseRenderer):
    def __init__(self) -> None:
        # TODO: This whole freaking this is broken
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.l = 10
        self.starting_color = Color(r=255, g=165, b=0)

    def _change_starting_point(self, width):
        self.starting_point = random.randint(0, width)
        self.current_y = 0

    def initialize(self, window: pygame.Surface, clock: pygame.time.Clock, peripheral_manager: PeripheralManager, orientation: Orientation,):
        self._change_starting_point(width=window.get_width())
        self.current_y = random.randint(0, 20)
        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()

        # Move one unit
        self.current_y += 1

        # Now draw a rain drop
        # It should decrease the saturation, but also dim

        window.set_at((self.starting_point, self.current_y), self.starting_color)
        f = self.starting_color.dim(fraction=1 / self.l)
        window.set_at((self.starting_point + 1, self.current_y), f)
        window.set_at((self.starting_point - 1, self.current_y), f)
        for i in range(self.l):
            # Make a triangle:
            # Brightness
            #    -----
            # --/     \--

            # I want this to transition from Orange to Yellow as it moves, going through black as a center point
            final_color = list(self.starting_color)
            final_color = self.starting_color.dim(fraction=i / self.l)
            window.set_at((self.starting_point, self.current_y + i), final_color)
            window.set_at((self.starting_point, self.current_y - i), final_color)
            if i < 3:
                f = self.dim(self.starting_color, fraction=(i + 1) / self.l)
                window.set_at((self.starting_point + 1, self.current_y + i), f)
                window.set_at((self.starting_point - 1, self.current_y - i), f)

        if self.current_y > height:
            self._change_starting_point(width=width)


## More Ideas
# - Comets
