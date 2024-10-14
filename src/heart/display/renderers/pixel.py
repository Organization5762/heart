import random
from dataclasses import dataclass

from heart.display.renderers import BaseRenderer


class RandomPixel(BaseRenderer):
    def __init__(self, num_pixels=1) -> None:
        super().__init__()
        self.device_display_mode = "full"
        self.num_pixels = num_pixels

    def _initialize(self) -> None:
        self.initialized = True

    def process(self, window, clock) -> None:
        width, height = window.get_size()
        for _ in range(self.num_pixels):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)

            random_color = (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255),
            )
            window.set_at((x, y), random_color)


class Border(BaseRenderer):
    def __init__(self, border_width: int) -> None:
        # TODO: This whole freaking this is broken
        super().__init__()
        self.device_display_mode = "full"
        self.border_width = border_width
        self.color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        )

    def _initialize(self) -> None:
        self.initialized = True

    def process(self, window, clock) -> None:
        width, height = window.get_size()
        total_border_pixels = 2 * (width + height) - 4  # Total pixels in the border

        # Draw the border
        for x in range(width):
            for y in range(self.border_width):
                window.set_at((x, y), self.color)  # Top border
                window.set_at((x, height - 1 - y), self.color)  # Bottom border

        for y in range(height):
            for x in range(self.border_width):
                window.set_at((x, y), self.color)  # Left border
                window.set_at((width - 1 - x, y), self.color)  # Right border


class Rain(BaseRenderer):
    def __init__(self) -> None:
        # TODO: This whole freaking this is broken
        super().__init__()
        self.device_display_mode = "full"
        self.initialized = False
        self.l = 8
        self.starting_color = (173, 216, 230)

    def _change_starting_point(self, width):
        self.starting_point = random.randint(0, width)
        self.current_y = 0

    def clamp(self, min_value, max_value, value):
        return min(max(value, min_value), max_value)

    def process(self, window, clock) -> None:
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
            color = [self.clamp(0, 255, x - (x * (i / 5))) for x in self.starting_color]
            window.set_at((self.starting_point, self.current_y - i), color)

        if self.current_y > height:
            self._change_starting_point(width=width)


class Slinky(BaseRenderer):
    def __init__(self) -> None:
        # TODO: This whole freaking this is broken
        super().__init__()
        self.device_display_mode = "full"
        self.initialized = False
        self.l = 10
        self.starting_color = (255, 165, 0)

    def _change_starting_point(self, width):
        self.starting_point = random.randint(0, width)
        self.current_y = 0

    def clamp(self, min_value, max_value, value):
        return min(max(value, min_value), max_value)

    def dim(self, color, fraction):
        return [self.clamp(0, 255, x - (x * fraction)) for x in color]

    def process(self, window, clock) -> None:
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
        f = self.dim(self.starting_color, fraction=1 / self.l)
        window.set_at((self.starting_point + 1, self.current_y), f)
        window.set_at((self.starting_point - 1, self.current_y), f)
        for i in range(self.l):
            # Make a triangle:
            # Brightness
            #    -----
            # --/     \--

            # I want this to transition from Orange to Yellow as it moves, going through black as a center point
            final_color = list(self.starting_color)
            final_color = self.dim(self.starting_color, fraction=i / self.l)
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
