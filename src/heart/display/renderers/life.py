import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock
from scipy.ndimage import convolve

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


class Life(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

        self.kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])
        self.state = None
        self.seed = None

    def _update_grid(self, grid):
        # convolve the grid with the kernel to count neighbors
        neighbors = convolve(grid, self.kernel, mode="constant", cval=0)

        # apply the rules
        new_grid = (neighbors == 3) | (grid & (neighbors == 2))
        assert new_grid.shape == grid.shape, "Grid size must match"

        return new_grid.astype(int)

    def _maybe_update_seed(
        self, window: Surface, peripheral_manager: PeripheralManager
    ) -> None:
        try:
            switch = peripheral_manager.get_switch_state_consumer()
        except ValueError:
            return
        current_value = switch.get_rotational_value()
        if current_value != self.seed:
            self.seed = current_value
            self.state = np.random.choice([0, 1], size=window.get_size())

    def process(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._maybe_update_seed(window=window, peripheral_manager=peripheral_manager)
        self.state = self._update_grid(self.state)

        # if 1, make white, else make black
        # We need to project these all to 3 dimenesions
        updated_colors = np.repeat(self.state[:, :, np.newaxis], 3, axis=2) * 255
        pygame.surfarray.blit_array(window, updated_colors)

        assert self.state.shape == window.get_size(), "Grid size must match window size"
