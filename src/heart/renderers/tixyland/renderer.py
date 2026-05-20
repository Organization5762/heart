import colorsys
from typing import Callable

import numpy as np
import pygame

from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.tixyland.provider import TixylandStateProvider
from heart.renderers.tixyland.state import TixylandState
from heart.runtime.display_context import DisplayContext


class Tixyland(StatefulBaseRenderer[TixylandState]):
    def __init__(
        self,
        fn: Callable[[float, np.ndarray, np.ndarray, np.ndarray], np.ndarray],
        builder: TixylandStateProvider | None = None,
        state: TixylandState | None = None,
    ) -> None:
        self._fn = fn
        super().__init__(builder=builder, state=state)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        state = self.state
        time_value = state.time_seconds

        h, w = window.get_height(), window.get_width()
        X, Y = np.meshgrid(np.arange(w), np.arange(h))
        flat_indices = X + Y * w + state.seed * 997

        numpy_output = self._fn(
            time_value,
            flat_indices,
            Y + state.seed * 17,
            X + state.seed * 31,
        )
        numpy_output = np.clip(numpy_output, -1, 1).astype(np.float16)
        mag = np.abs(numpy_output)
        primary, secondary = _palette(state.hue_degrees)

        # Compute red and white intensity arrays, ensuring correct float32 dtype
        low = (mag[..., None] * primary * 255).astype(
            np.uint32
        )
        high = (mag[..., None] * secondary * 255).astype(
            np.uint32
        )

        # Shape: (h, w, 3), dtype: uint32
        rgb = np.where(numpy_output[..., None] < 0, low, high).astype(np.uint32)

        # Make sure the array is shape (w, h, 3) for blit_array
        arr_for_blit = np.transpose(rgb, (1, 0, 2))

        pygame.surfarray.blit_array(window.screen, arr_for_blit)


def _palette(hue_degrees: float) -> tuple[np.ndarray, np.ndarray]:
    hue = (hue_degrees % 360.0) / 360.0
    primary = np.array(colorsys.hsv_to_rgb(hue, 1.0, 1.0), dtype=np.float32)
    secondary = np.array(
        colorsys.hsv_to_rgb(hue, 0.35, 1.0),
        dtype=np.float32,
    )
    return (primary, secondary)
