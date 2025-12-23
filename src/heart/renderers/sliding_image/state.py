from __future__ import annotations

from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class SlidingImageState:
    offset: int = 0
    speed: int = 1
    width: int = 0
    image: pygame.Surface | None = None


@dataclass(frozen=True)
class SlidingRendererState:
    offset: int = 0
    speed: int = 1
    width: int = 0
