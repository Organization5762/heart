import random

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager


class RandomPixel(BaseRenderer):
    def __init__(self, num_pixels=1) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.num_pixels = num_pixels

    def _initialize(self) -> None:
        self.initialized = True

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        for _ in range(self.num_pixels):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)

            random_color = Color.random()
            window.set_at((x, y), random_color._as_tuple())


class Border(BaseRenderer):
    def __init__(self, width: int, color: Color | None = None) -> None:
        # TODO: This whole freaking this is broken
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.width = width
        self.color = color or Color.random()

    def _initialize(self) -> None:
        self.initialized = True

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
        self.initialized = False
        self.l = 8
        self.starting_color = Color(r=173, g=216, b=230)

    def _change_starting_point(self, width):
        self.starting_point = random.randint(0, width)
        self.current_y = 0

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        if not self.initialized:
            self._change_starting_point(width=width)
            self.current_y = random.randint(0, 20)
            self.initialized = True

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
        self.initialized = False
        self.l = 10
        self.starting_color = Color(r=255, g=165, b=0)

    def _change_starting_point(self, width):
        self.starting_point = random.randint(0, width)
        self.current_y = 0

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        if not self.initialized:
            self._change_starting_point(width=width)
            self.current_y = random.randint(0, 20)
            self.initialized = True

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
class PacmanGhostRenderer(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.initialized = False
        self.device_display_mode = DeviceDisplayMode.FULL
        self.last_corner = None  # Initialize the corner at the beginning

    def _initialize(self, window: pygame.Surface) -> None:
        self.initialized = True
        self.screen_width, self.screen_height = window.get_size()
        self.blood = True
        self._initialize_corner()
        self.pacmanIdx = 0
        self.switch_pacman = True

    def _initialize_corner(self) -> None:
        import random

        corners = ["top_left", "top_right"]
        corner = random.choice(corners)
        self.last_corner = corner

        self.blood = not self.blood

        if corner == "top_left":
            self.x = -50
            self.y = 16
            self.reverse = False
        elif corner == "top_right":
            self.x = self.screen_width + 50
            self.y = 16
            self.reverse = True
        elif corner == "bottom_left":
            self.x = -50
            self.y = self.screen_height - 48
            self.reverse = False
        elif corner == "bottom_right":
            self.x = self.screen_width + 50
            self.y = self.screen_height - 48
            self.reverse = True

        if self.reverse:
            self.ghost1 = pygame.transform.flip(
                Loader.load(
                        "scaredghost1.png" if self.blood else "pinkghost.png"
                ),
                True,
                False,
            )
            self.ghost2 = pygame.transform.flip(
                Loader.load(
                        "scaredghost2.png" if self.blood else "blueghost.png"
                ),
                True,
                False,
            )
            self.ghost3 = pygame.transform.flip(
                Loader.load(
                        "scaredghost1.png" if self.blood else "redghost.png"
                ),
                True,
                False,
            )
        else:
            self.ghost1 = Loader.load(
                    "scaredghost1.png" if self.blood else "pinkghost.png"
            )
            self.ghost2 = Loader.load(
                    "scaredghost2.png" if self.blood else "blueghost.png"
            )
            self.ghost3 = Loader.load(
                    "scaredghost1.png" if self.blood else "redghost.png"
            )

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.initialized:
            self._initialize(window=window)

        # Update position
        if self.reverse:
            self.x -= 5
        else:
            self.x += 5

        if self.x > self.screen_width + 50 or self.x < -150:
            self._initialize_corner()

        if self.switch_pacman:
            self.pacmanIdx = (self.pacmanIdx + 1) % 3
            self.switch_pacman = False
        else:
            self.switch_pacman = True

        if self.blood:
            self.pacman = Loader.load(
                f"bloodpac{self.pacmanIdx + 1}.png"
            )
        else:
            self.pacman = Loader.load(
                f"pac{self.pacmanIdx + 1}.png"
            )

        if (self.reverse and not self.blood) or (self.blood and not self.reverse):
            self.pacman = pygame.transform.flip(self.pacman, True, False)

        # Draw the sprite
        if (not self.blood and self.reverse) or (self.blood and not self.reverse):
            window.blit(self.pacman, (self.x, self.y))
            window.blit(self.ghost1, (self.x + 32, self.y))
            window.blit(self.ghost2, (self.x + 64, self.y))
            window.blit(self.ghost3, (self.x + 96, self.y))
        if self.blood and self.reverse or (not self.blood and not self.reverse):
            window.blit(self.ghost3, (self.x, self.y))
            window.blit(self.ghost2, (self.x + 32, self.y))
            window.blit(self.ghost1, (self.x + 64, self.y))
            window.blit(self.pacman, (self.x + 96, self.y))
