from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlidingImageState:
    offset: int = 0
    speed: int = 1
    width: int = 0


@dataclass(frozen=True)
class SlidingRendererState:
    offset: int = 0
    speed: int = 1
    width: int = 0
