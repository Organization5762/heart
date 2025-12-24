
import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.modules.life.provider import LifeStateProvider
from heart.renderers.modules.life.state import LifeState


class Life(StatefulBaseRenderer[LifeState]):
    def __init__(self, builder: LifeStateProvider) -> None:
        super().__init__(builder=builder)
        # AtomicBaseRenderer reinitializes device_display_mode; restore FULL to
        # preserve the original renderer behaviour of operating on the entire
        # device surface rather than the per-tile mirrored view.
        self.device_display_mode = DeviceDisplayMode.FULL

    def real_process(
        self,
        window: Surface,
        clock: Clock,
        orientation: Orientation,
    ) -> None:
        # if 1, make white, else make black
        # We need to project these all to 3 dimensions
        updated_colors = np.repeat(self.state.grid[:, :, np.newaxis], 3, axis=2) * 255
        pygame.surfarray.blit_array(window, updated_colors)
        assert self.state.grid.shape == window.get_size(), "Grid size must match window size"