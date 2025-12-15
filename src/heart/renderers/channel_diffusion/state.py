from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ChannelDiffusionState:
    grid: np.ndarray
