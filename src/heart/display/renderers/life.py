from dataclasses import dataclass

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock
from scipy.ndimage import convolve

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class LifeState:
    grid: np.ndarray


class Life(AtomicBaseRenderer[LifeState]):
    def __init__(self) -> None:
        self.kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])

        AtomicBaseRenderer.__init__(self)
        # AtomicBaseRenderer reinitializes device_display_mode; restore FULL to
        # preserve the original renderer behaviour of operating on the entire
        # device surface rather than the per-tile mirrored view.
        self.device_display_mode = DeviceDisplayMode.FULL

    def _update_grid(self, grid):
        # convolve the grid with the kernel to count neighbors
        neighbors = convolve(grid, self.kernel, mode="constant", cval=0)

        # apply the rules
        new_grid = (neighbors == 3) | (grid & (neighbors == 2))
        assert new_grid.shape == grid.shape, "Grid size must match"

        return new_grid.astype(int)

    def real_process(
        self,
        window: Surface,
        clock: Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state
        grid = state.grid
        next_grid = self._update_grid(grid)
        self.state.grid = next_grid

        # if 1, make white, else make black
        # We need to project these all to 3 dimenesions
        updated_colors = np.repeat(next_grid[:, :, np.newaxis], 3, axis=2) * 255
        pygame.surfarray.blit_array(window, updated_colors)

        assert next_grid.shape == window.get_size(), "Grid size must match window size"

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> LifeState:
        def create_new_grid():
            return np.random.choice([0, 1], size=window.get_size())

        def update_grid(v):
            self.state.grid = create_new_grid()
        
        source = peripheral_manager.get_main_switch_subscription()

        source.subscribe(
            on_next = update_grid,
            on_error = lambda e: print("Error Occurred: {0}".format(e)),
            on_completed = lambda: print("Done!"),
        )
        
        return LifeState(
            grid=create_new_grid()
        )

