from __future__ import annotations

from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class SlidingImageState:
    offset: int = 0
    speed: int = 1
    width: int = 0
    image: pygame.Surface | None = None

    def advance(self) -> "SlidingImageState":
        if self.width <= 0:
            return self

        offset = (self.offset + self.speed) % self.width
        return SlidingImageState(
            offset=offset, speed=self.speed, width=self.width, image=self.image
        )


@dataclass(frozen=True)
class SlidingRendererState:
    offset: int = 0
    speed: int = 1
    width: int = 0

    def advance(self) -> "SlidingRendererState":
        if self.width <= 0:
            return self

        offset = (self.offset + self.speed) % self.width
        return SlidingRendererState(offset=offset, speed=self.speed, width=self.width)
