from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DopplerState:
    position: np.ndarray
    velocity: np.ndarray
    previous_velocity: np.ndarray
    last_dt: float
