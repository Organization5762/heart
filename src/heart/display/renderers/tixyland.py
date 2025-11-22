from dataclasses import dataclass
from typing import Callable

import numpy as np
import pygame

from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class TixylandState:
    """Mutable timing state for the Tixy-inspired shader."""

    time_since_last_update: float = 0.0


class Tixyland(AtomicBaseRenderer[TixylandState]):
    def __init__(
        self,
        fn: Callable[[float, np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    ) -> None:
        self._fn = fn
        AtomicBaseRenderer.__init__(self)

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
        return TixylandState()

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        time_since_last_update = self.state.time_since_last_update + clock.get_time()
        self.update_state(time_since_last_update=time_since_last_update)
        # Convert from ms to seconds
        time_value = time_since_last_update / 1000

        h, w = window.get_height(), window.get_width()
        X, Y = np.meshgrid(np.arange(w), np.arange(h))
        flat_indices = X + Y * w

        numpy_output = self._fn(time_value, flat_indices, Y, X)
        numpy_output = np.clip(numpy_output, -1, 1)
        numpy_output = numpy_output.astype(np.float16)
        mag = np.abs(numpy_output)

        red = mag[..., None] * np.array([1, 0, 0]) * 255
        white = mag[..., None] * np.array([1, 1, 1]) * 200

        rgb = np.where(numpy_output[..., None] < 0, red, white)

        pygame.surfarray.blit_array(window, rgb)
