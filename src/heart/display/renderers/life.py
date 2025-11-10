from dataclasses import dataclass

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock
from scipy.ndimage import convolve

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.internal import SwitchStateConsumer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class LifeState:
    grid: np.ndarray | None = None
    seed: float | None = None


class Life(SwitchStateConsumer, AtomicBaseRenderer[LifeState]):
    def __init__(self) -> None:
        SwitchStateConsumer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

        self.kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])

        AtomicBaseRenderer.__init__(self)

    def _update_grid(self, grid):
        # convolve the grid with the kernel to count neighbors
        neighbors = convolve(grid, self.kernel, mode="constant", cval=0)

        # apply the rules
        new_grid = (neighbors == 3) | (grid & (neighbors == 2))
        assert new_grid.shape == grid.shape, "Grid size must match"

        return new_grid.astype(int)

    def _maybe_update_seed(self, window: Surface) -> None:
        current_value = self.get_switch_state().rotational_value
        state = self.state
        if current_value != state.seed or state.grid is None:
            grid = np.random.choice([0, 1], size=window.get_size())
            self.update_state(seed=current_value, grid=grid)

    def initialize(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self.bind_switch(peripheral_manager)
        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._maybe_update_seed(window=window)
        state = self.state
        grid = state.grid
        if grid is None:
            return

        next_grid = self._update_grid(grid)
        self.update_state(grid=next_grid)

        # if 1, make white, else make black
        # We need to project these all to 3 dimenesions
        updated_colors = np.repeat(next_grid[:, :, np.newaxis], 3, axis=2) * 255
        pygame.surfarray.blit_array(window, updated_colors)

        assert next_grid.shape == window.get_size(), "Grid size must match window size"

    def _create_initial_state(self) -> LifeState:
        return LifeState()

