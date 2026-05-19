from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from heart.display.color import Color


@dataclass(frozen=True)
class RandomPixelState:
    color: Color
    pixels: np.ndarray
