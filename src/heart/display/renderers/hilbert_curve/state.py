from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

BoundingBox = tuple[float, float, float, float]
Phase = Literal["morph", "zoom"]


@dataclass(frozen=True)
class HilbertCurveState:
    width: int
    height: int
    xmargin: int
    ymargin: int
    resample_count: int
    max_order: int
    current_order: int
    next_order: int
    current_curve: np.ndarray
    target_curve: np.ndarray
    next_points: np.ndarray
    transition_state: Phase
    morph_start_time: float
    zoom_start_time: float | None
    zoom_bbox: BoundingBox | None
    target_scale: float | None
    frame_curve: np.ndarray
