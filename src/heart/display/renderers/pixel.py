from dataclasses import dataclass
from heart.display.renderers import BaseRenderer
import random

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
            
            random_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            window.set_at((x, y), random_color)

class Border(BaseRenderer):
    def __init__(self, border_width: int) -> None:
        # TODO: This whole freaking this is broken
        super().__init__()
        self.device_display_mode = "full"
        self.border_width = border_width
        self.color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

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