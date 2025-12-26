from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pygame

from heart.utilities.env import Configuration, SpritesheetFrameCacheStrategy


class Spritesheet:
    def __init__(self, filename: str | Path) -> None:
        path = Path(filename)
        if not path.exists():
            raise ValueError(f"'{path}' does not exist.")

        if not path.is_file():
            raise ValueError(f"'{path}' is not a file.")

        with path.open("rb") as file_handle:
            self.sheet = pygame.image.load(file_handle).convert_alpha()
        self._frame_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}
        self._scaled_cache: dict[tuple[int, int, int, int, int, int], pygame.Surface] = {}

    def get_size(self) -> tuple[int, int]:
        return self.sheet.get_size()

    def image_at(self, rectangle: tuple[int, int, int, int]) -> pygame.Surface:
        rect = pygame.Rect(rectangle)
        cache_key = (rect.x, rect.y, rect.width, rect.height)
        strategy = Configuration.spritesheet_frame_cache_strategy()
        if strategy in {
            SpritesheetFrameCacheStrategy.FRAMES,
            SpritesheetFrameCacheStrategy.SCALED,
        }:
            cached = self._frame_cache.get(cache_key)
            if cached is not None:
                return cached

        image = pygame.Surface(rect.size, pygame.SRCALPHA)
        image.blit(self.sheet, (0, 0), rect)
        if strategy in {
            SpritesheetFrameCacheStrategy.FRAMES,
            SpritesheetFrameCacheStrategy.SCALED,
        }:
            self._frame_cache[cache_key] = image
        return image

    def image_at_scaled(
        self, rectangle: tuple[int, int, int, int], size: tuple[int, int]
    ) -> pygame.Surface:
        rect = pygame.Rect(rectangle)
        width, height = size
        cache_key = (rect.x, rect.y, rect.width, rect.height, width, height)
        strategy = Configuration.spritesheet_frame_cache_strategy()
        if strategy == SpritesheetFrameCacheStrategy.SCALED:
            cached = self._scaled_cache.get(cache_key)
            if cached is not None:
                return cached

        image = self.image_at(rect)
        scaled = pygame.transform.scale(image, (width, height))
        if strategy == SpritesheetFrameCacheStrategy.SCALED:
            self._scaled_cache[cache_key] = scaled
        return scaled

    def images_at(
        self, rects: Iterable[tuple[int, int, int, int]]
    ) -> list[pygame.Surface]:
        """Load multiple images by supplying a list of coordinates."""

        return [self.image_at(rect) for rect in rects]

    def load_strip(
        self, rect: tuple[int, int, int, int], image_count: int
    ) -> list[pygame.Surface]:
        """Load a strip of images and return them as a list."""

        rectangles = [
            (rect[0] + rect[2] * index, rect[1], rect[2], rect[3])
            for index in range(image_count)
        ]
        return self.images_at(rectangles)
