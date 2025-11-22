import random
from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
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


@dataclass
class PacmanGhostState:
    screen_width: int = 0
    screen_height: int = 0
    last_corner: str | None = None
    blood: bool = True
    reverse: bool = False
    x: int = 0
    y: int = 0
    pacman_idx: int = 0
    switch_pacman: bool = True


class RandomPixel(AtomicBaseRenderer[RandomPixelState]):
    def __init__(self, num_pixels: int = 1, color: Color | None = None) -> None:
        self.num_pixels = num_pixels
        self._initial_color = color
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        for _ in range(self.num_pixels):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)

            random_color = self.state.color or Color.random()
            window.set_at((x, y), random_color._as_tuple())

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
        return RandomPixelState(color=self._initial_color)

    def set_color(self, color: Color | None) -> None:
        self.update_state(color=color)


class Border(AtomicBaseRenderer[BorderState]):
    def __init__(
        self,
        width: int,
        color: Color | None = None,
        display_mode: DeviceDisplayMode = DeviceDisplayMode.FULL,
    ) -> None:
        # TODO: This whole freaking this is broken
        self._initial_color = color or Color.random()
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = display_mode
        self.width = width

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        pygame.draw.rect(
            window,
            self.state.color._as_tuple(),
            (0, 0, width, height),
            self.width,
        )

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
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

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
        width, height = window.get_size()
        return RainState(
            starting_point=random.randint(0, width),
            current_y=0,
        )

    def _change_starting_point(self, width, *, current_y: int = 0) -> None:
        self.update_state(
            starting_point=random.randint(0, width),
            current_y=current_y,
        )

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()

        # Move one unit
        state = self.state
        new_y = state.current_y + 1

        # Now draw a rain drop
        # It should decrease the saturation, but also dim

        for i in range(self.l):
            color = self.starting_color.dim(fraction=i / self.l)
            window.set_at((state.starting_point, new_y - i), color)

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

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
        width, height = window.get_size()
        return SlinkyState(
            starting_point=random.randint(0, width),
            current_y=0,
        )

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        # Move one unit
        state = self.state
        new_y = state.current_y + 1

        # Now draw a rain drop
        # It should decrease the saturation, but also dim

        window.set_at((state.starting_point, new_y), self.starting_color)
        f = self.starting_color.dim(fraction=1 / self.l)
        window.set_at((state.starting_point + 1, new_y), f)
        window.set_at((state.starting_point - 1, new_y), f)
        for i in range(self.l):
            # Make a triangle:
            # Brightness
            #    -----
            # --/     \--

            # I want this to transition from Orange to Yellow as it moves, going through black as a center point
            final_color = list(self.starting_color)
            final_color = self.starting_color.dim(fraction=i / self.l)
            window.set_at((state.starting_point, new_y + i), final_color)
            window.set_at((state.starting_point, new_y - i), final_color)
            if i < 3:
                f = self.dim(self.starting_color, fraction=(i + 1) / self.l)
                window.set_at((state.starting_point + 1, new_y + i), f)
                window.set_at((state.starting_point - 1, new_y - i), f)

        if new_y > height:
            self._change_starting_point(width=width)
        else:
            self.update_state(current_y=new_y)


## More Ideas
class PacmanGhostRenderer(AtomicBaseRenderer[PacmanGhostState]):
    def __init__(self) -> None:
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL
        self.ghost1: pygame.Surface | None = None
        self.ghost2: pygame.Surface | None = None
        self.ghost3: pygame.Surface | None = None
        self.pacman: pygame.Surface | None = None

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
        width, height = window.get_size()
        return PacmanGhostState(
            screen_width=width,
            screen_height=height,
            blood=True,
            pacman_idx=0,
            switch_pacman=True,
        )

    def _initialize_corner(self) -> None:
        state = self.state
        corners = ["top_left", "top_right", "bottom_left", "bottom_right"]
        corner = random.choice(corners)
        blood = not state.blood
        screen_width = state.screen_width
        screen_height = state.screen_height

        if corner == "top_left":
            x = -50
            y = 16
            reverse = False
        elif corner == "top_right":
            x = screen_width + 50
            y = 16
            reverse = True
        elif corner == "bottom_left":
            x = -50
            y = screen_height - 48
            reverse = False
        else:
            x = screen_width + 50
            y = screen_height - 48
            reverse = True

        load = Loader.load
        if reverse:
            self.ghost1 = pygame.transform.flip(
                load("scaredghost1.png" if blood else "pinkghost.png"), True, False
            )
            self.ghost2 = pygame.transform.flip(
                load("scaredghost2.png" if blood else "blueghost.png"), True, False
            )
            self.ghost3 = pygame.transform.flip(
                load("scaredghost1.png" if blood else "redghost.png"), True, False
            )
        else:
            self.ghost1 = load("scaredghost1.png" if blood else "pinkghost.png")
            self.ghost2 = load("scaredghost2.png" if blood else "blueghost.png")
            self.ghost3 = load("scaredghost1.png" if blood else "redghost.png")

        self.update_state(
            last_corner=corner,
            blood=blood,
            reverse=reverse,
            x=x,
            y=y,
        )

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state
        screen_width = state.screen_width

        # Update position
        delta = -5 if state.reverse else 5
        new_x = state.x + delta

        if new_x > screen_width + 50 or new_x < -150:
            self._initialize_corner()
            state = self.state
            new_x = state.x
        
        if state.switch_pacman:
            pacman_idx = (state.pacman_idx + 1) % 3
        else:
            pacman_idx = state.pacman_idx
        new_switch = not state.switch_pacman

        self.update_state(x=new_x, pacman_idx=pacman_idx, switch_pacman=new_switch)
        state = self.state

        if state.blood:
            self.pacman = Loader.load(f"bloodpac{state.pacman_idx + 1}.png")
        else:
            self.pacman = Loader.load(f"pac{state.pacman_idx + 1}.png")

        if (state.reverse and not state.blood) or (state.blood and not state.reverse):
            self.pacman = pygame.transform.flip(self.pacman, True, False)

        # Draw the sprite
        x = state.x
        y = state.y
        if (not state.blood and state.reverse) or (state.blood and not state.reverse):
            window.blit(self.pacman, (x, y))
            if self.ghost1 and self.ghost2 and self.ghost3:
                window.blit(self.ghost1, (x + 32, y))
                window.blit(self.ghost2, (x + 64, y))
                window.blit(self.ghost3, (x + 96, y))
        if state.blood and state.reverse or (not state.blood and not state.reverse):
            if self.ghost1 and self.ghost2 and self.ghost3:
                window.blit(self.ghost3, (x, y))
                window.blit(self.ghost2, (x + 32, y))
                window.blit(self.ghost1, (x + 64, y))
            window.blit(self.pacman, (x + 96, y))