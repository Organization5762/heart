from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class SlideTransitionState:
    peripheral_manager: PeripheralManager
    fraction_offset: float = 0.0
    sliding: bool = True


class SlideTransitionMode(StrEnum):
    SLIDE = "slide"
    STATIC = "static"
    GAUSSIAN = "gaussian"


DEFAULT_STATIC_MASK_STEPS = 20
DEFAULT_GAUSSIAN_SIGMA = 1.5
