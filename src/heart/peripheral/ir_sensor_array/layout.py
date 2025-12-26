"""Layout helpers for IR sensor arrays."""

from __future__ import annotations

import math

from .constants import DEFAULT_RADIAL_LAYOUT_RADIUS


def radial_layout(radius: float = DEFAULT_RADIAL_LAYOUT_RADIUS) -> list[list[float]]:
    """Return sensor positions for a square radial layout."""

    half = radius / math.sqrt(2)
    vertical = radius * 0.15
    return [
        [-half, 0.0, vertical],
        [0.0, half, -vertical],
        [half, 0.0, vertical],
        [0.0, -half, -vertical],
    ]
