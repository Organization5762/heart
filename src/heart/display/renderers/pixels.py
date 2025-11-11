import random
from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class RandomPixelState:
    color: Color | None


@dataclass
class BorderState:
    color: Color


@dataclass
class RainState:
    starting_point: int = 0
    current_y: int = 0


@dataclass
class SlinkyState:
    starting_point: int = 0
    current_y: int = 0


class RandomPixel(AtomicBaseRenderer[RandomPixelState]):
    def __init__(
        self, num_pixels=1, color: Color | None = None, brightness: float = 1.0
    ) -> None:
        self._initial_color = color
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL
        self.num_pixels = num_pixels
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
        state = self.state
        random_color = state.color or Color.random()
        color_value = [int(x * self.brightness) for x in random_color._as_tuple()]
        for x, y in pixels:
            window.set_at((x, y), color_value)

    def _create_initial_state(self) -> RandomPixelState:
        return RandomPixelState(color=self._initial_color)

    def set_color(self, color: Color | None) -> None:
        self.update_state(color=color)


class Border(AtomicBaseRenderer[BorderState]):
    def __init__(self, width: int, color: Color | None = None) -> None:
        # TODO: This whole freaking this is broken
        self._initial_color = color or Color.random()
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL
        self.width = width

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()

        # Draw the border
        color_value = self.state.color._as_tuple()
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

    def _create_initial_state(self) -> BorderState:
        return BorderState(color=self._initial_color)

    def set_color(self, color: Color) -> None:
        self.update_state(color=color)


class Rain(AtomicBaseRenderer[RainState]):
    def __init__(self) -> None:
        # TODO: This whole freaking this is broken
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL
        self.l = 8
        self.starting_color = Color(r=173, g=216, b=230)

    def _create_initial_state(self) -> RainState:
        return RainState()

    def _change_starting_point(self, width, *, current_y: int = 0) -> None:
        self.update_state(
            starting_point=random.randint(0, width),
            current_y=current_y,
        )

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        initial_y = random.randint(0, 20)
        self._change_starting_point(
            width=window.get_width(), current_y=initial_y
        )
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
        state = self.state
        new_y = state.current_y + 1
        starting_point = state.starting_point

        # Now draw a rain drop
        # It should decrease the saturation, but also dim

        for i in range(self.l):
            color = self.starting_color.dim(fraction=i / self.l)
            window.set_at((starting_point, new_y - i), color)

        if new_y > height:
            self._change_starting_point(width=width)
        else:
            self.update_state(current_y=new_y)


class Slinky(AtomicBaseRenderer[SlinkyState]):
    def __init__(self) -> None:
        # TODO: This whole freaking this is broken
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL
        self.l = 10
        self.starting_color = Color(r=255, g=165, b=0)

    def _create_initial_state(self) -> SlinkyState:
        return SlinkyState()

    def _change_starting_point(self, width, *, current_y: int = 0) -> None:
        self.update_state(
            starting_point=random.randint(0, width),
            current_y=current_y,
        )

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        initial_y = random.randint(0, 20)
        self._change_starting_point(
            width=window.get_width(), current_y=initial_y
        )
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
        state = self.state
        new_y = state.current_y + 1
        starting_point = state.starting_point

        # Now draw a rain drop
        # It should decrease the saturation, but also dim

        window.set_at((starting_point, new_y), self.starting_color)
        f = self.starting_color.dim(fraction=1 / self.l)
        window.set_at((starting_point + 1, new_y), f)
        window.set_at((starting_point - 1, new_y), f)
        for i in range(self.l):
            # Make a triangle:
            # Brightness
            #    -----
            # --/     \--

            # I want this to transition from Orange to Yellow as it moves, going through black as a center point
            final_color = list(self.starting_color)
            final_color = self.starting_color.dim(fraction=i / self.l)
            window.set_at((starting_point, new_y + i), final_color)
            window.set_at((starting_point, new_y - i), final_color)
            if i < 3:
                f = self.dim(self.starting_color, fraction=(i + 1) / self.l)
                window.set_at((starting_point + 1, new_y + i), f)
                window.set_at((starting_point - 1, new_y - i), f)

        if new_y > height:
            self._change_starting_point(width=width)
        else:
            self.update_state(current_y=new_y)


## More Ideas
# - Comets
