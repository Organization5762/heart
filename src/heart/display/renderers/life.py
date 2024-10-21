import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock
from scipy.ndimage import convolve

from heart.display.renderers import BaseRenderer
from heart.environment import DeviceDisplayMode


class Life(BaseRenderer):
    def __init__(self) -> None:
        self.device_display_mode = DeviceDisplayMode.FULL

        self.kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])
        self.state = None

    def _update_grid(self, grid):
        # convolve the grid with the kernel to count neighbors
        neighbors = convolve(grid, self.kernel, mode="constant", cval=0)

        # apply the rules
        new_grid = (neighbors == 3) | (grid & (neighbors == 2))
        assert new_grid.shape == grid.shape, "Grid size must match"

        return new_grid.astype(int)

    def process(self, window: Surface, clock: Clock) -> None:
        if self.state is None:
            # TODO: set a non-random seed
            self.state = np.random.choice([0, 1], size=window.get_size())
        self.state = self._update_grid(self.state)

        # if 1, make white, else make black
        # We need to project these all to 3 dimenesions
        updated_colors = np.repeat(self.state[:, :, np.newaxis], 3, axis=2) * 255
        pygame.surfarray.blit_array(window, updated_colors)

        assert self.state.shape == window.get_size(), "Grid size must match window size"
