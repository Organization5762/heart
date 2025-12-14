from typing import Callable

import numpy as np
import pygame

from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.tixyland.provider import TixylandStateProvider
from heart.renderers.tixyland.state import TixylandState


class Tixyland(StatefulBaseRenderer[TixylandState]):
    def __init__(
        self,
        builder: TixylandStateProvider,
        fn: Callable[[float, np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    ) -> None:
        self._fn = fn
        super().__init__(builder=builder)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        time_value = self.state.time_seconds

        h, w = window.get_height(), window.get_width()
        X, Y = np.meshgrid(np.arange(w), np.arange(h))
        flat_indices = X + Y * w

        numpy_output = self._fn(time_value, flat_indices, Y, X)
        numpy_output = np.clip(numpy_output, -1, 1).astype(np.float16)
        mag = np.abs(numpy_output)

        red = mag[..., None] * np.array([1, 0, 0]) * 255
        white = mag[..., None] * np.array([1, 1, 1]) * 200

        rgb = np.where(numpy_output[..., None] < 0, red, white)

        pygame.surfarray.blit_array(window, rgb)
