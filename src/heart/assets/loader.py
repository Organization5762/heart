import json
import os
from functools import cache
from pathlib import Path
from typing import Any

import pygame

from heart.utilities.paths import heart_asset_path


class Loader:
    @classmethod
    def resolve_path(cls, path: str | os.PathLike[str]) -> Path:
        """Return the absolute path to a file in ``src/heart/assets``."""

        return heart_asset_path(path)

    @classmethod
    def _resolve_path(cls, path):
        return os.fspath(cls.resolve_path(path))

    @classmethod
    @cache
    def load(cls, path: str):
        return pygame.image.load(cls._resolve_path(path))

    @classmethod
    def load_spirtesheet(cls, path):
        resolved_path = cls._resolve_path(path)
        return spritesheet(resolved_path)

    @classmethod
    def load_animation(cls, path):
        return Animation(cls._resolve_path(path), 100)

    @classmethod
    def load_font(cls, path, font_size: int = 10):
        return pygame.font.Font(cls._resolve_path(path), size=font_size)

    @classmethod
    def load_json(cls, path) -> dict[str, Any]:
        resolved_path = cls._resolve_path(path)
        with open(resolved_path, "r") as fp:
            return json.load(fp)


# https://www.pygame.org/wiki/Spritesheet
# I copied this from here it is kinda meh lol
class spritesheet(object):
    def __init__(self, filename: str):
        if not os.path.exists(filename):
            raise ValueError(f"'{filename}' does not exist.")

        if not os.path.isfile(filename):
            raise ValueError(f"'{filename}' is not a file.")

        with open(filename, "rb") as f:
            self.sheet = pygame.image.load(f).convert_alpha()

    def get_size(self):
        return self.sheet.get_size()

    def image_at(self, rectangle):
        rect = pygame.Rect(rectangle)
        image = pygame.Surface(rect.size, pygame.SRCALPHA)
        image.blit(self.sheet, (0, 0), rect)
        return image

    def images_at(self, rects):
        "Loads multiple images, supply a list of coordinates"
        return [self.image_at(rect) for rect in rects]

    def load_strip(self, rect, image_count):
        "Loads a strip of images and returns them as a list"
        tups = [
            (rect[0] + rect[2] * x, rect[1], rect[2], rect[3])
            for x in range(image_count)
        ]
        return self.images_at(tups)


class Animation:
    def __init__(self, file_path: str, width: int) -> None:
        self.spritesheet = Loader.load_spirtesheet(file_path)

        image_size = self.spritesheet.sheet.get_size()
        self.number_of_frames = image_size[0] / width

        self.key_frames = [
            (width * i, 0, width, image_size[1])
            for i in range(int(self.number_of_frames))
        ]
        self.current_frame = 0
        self.ms_since_last_update = None
        self.ms_per_frame = 25

    def step(self, window, clock):
        if (
            self.ms_since_last_update is None
            or self.ms_since_last_update > self.ms_per_frame
        ):
            if self.current_frame >= self.number_of_frames - 1:
                self.current_frame = 0
            else:
                self.current_frame += 1

            self.ms_since_last_update = 0

        image = self.spritesheet.image_at(self.key_frames[self.current_frame])
        self.ms_since_last_update += clock.get_time()
        return image
