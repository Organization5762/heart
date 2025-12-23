from __future__ import annotations

from dataclasses import dataclass

from heart.display.color import Color


@dataclass(frozen=True)
class RandomPixelState:
    color: Color
    pixels: tuple[tuple[int, int], ...]
