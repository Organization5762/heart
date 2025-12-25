import json
from os import PathLike
from pathlib import Path
from typing import Any

import pygame

from heart.assets.cache import AssetCache
from heart.utilities.env import (AssetCacheStrategy, Configuration,
                                 SpritesheetFrameCacheStrategy)


class Loader:
    _image_cache: AssetCache[Path, pygame.Surface] | None = None
    _spritesheet_cache: AssetCache[Path, "spritesheet"] | None = None
    _metadata_cache: AssetCache[Path, dict[str, Any]] | None = None

    @classmethod
    def _resolve_cache_strategy(cls) -> AssetCacheStrategy:
        return Configuration.asset_cache_strategy()

    @classmethod
    def _cache_max_entries(cls) -> int:
        return Configuration.asset_cache_max_entries()

    @classmethod
    def _get_spritesheet_cache(cls) -> AssetCache[Path, "spritesheet"] | None:
        strategy = cls._resolve_cache_strategy()
        if strategy not in {AssetCacheStrategy.SPRITESHEETS, AssetCacheStrategy.ALL}:
            return None
        if cls._spritesheet_cache is None:
            cls._spritesheet_cache = AssetCache(
                cls._cache_max_entries(), name="spritesheets"
            )
        return cls._spritesheet_cache

    @classmethod
    def _get_image_cache(cls) -> AssetCache[Path, pygame.Surface] | None:
        strategy = cls._resolve_cache_strategy()
        if strategy not in {AssetCacheStrategy.IMAGES, AssetCacheStrategy.ALL}:
            return None
        if cls._image_cache is None:
            cls._image_cache = AssetCache(cls._cache_max_entries(), name="images")
        return cls._image_cache

    @classmethod
    def _get_metadata_cache(cls) -> AssetCache[Path, dict[str, Any]] | None:
        strategy = cls._resolve_cache_strategy()
        if strategy not in {AssetCacheStrategy.METADATA, AssetCacheStrategy.ALL}:
            return None
        if cls._metadata_cache is None:
            cls._metadata_cache = AssetCache(
                cls._cache_max_entries(), name="metadata"
            )
        return cls._metadata_cache

    @classmethod
    def reset_caches(cls) -> None:
        cls._image_cache = None
        cls._spritesheet_cache = None
        cls._metadata_cache = None

    @classmethod
    def resolve_path(cls, path: str | PathLike[str]) -> Path:
        """Return the absolute path to a file in ``src/heart/assets``."""

        return Path(__file__).resolve().parent / Path(path)

    @classmethod
    def _resolve_path(cls, path: str | PathLike[str]) -> Path:
        return cls.resolve_path(path)

    @classmethod
    def load(cls, path: str | PathLike[str]) -> pygame.Surface:
        resolved_path = cls._resolve_path(path)
        cache = cls._get_image_cache()
        if cache is not None:
            cached = cache.get(resolved_path)
            if cached is not None:
                return cached
        loaded = pygame.image.load(resolved_path)
        if cache is not None:
            cache.set(resolved_path, loaded)
        return loaded

    @classmethod
    def load_spirtesheet(cls, path: str | PathLike[str]) -> "spritesheet":
        resolved_path = cls._resolve_path(path)
        cache = cls._get_spritesheet_cache()
        if cache is not None:
            cached = cache.get(resolved_path)
            if cached is not None:
                return cached
        loaded = spritesheet(resolved_path)
        if cache is not None:
            cache.set(resolved_path, loaded)
        return loaded

    @classmethod
    def load_animation(cls, path: str | PathLike[str]) -> "Animation":
        return Animation(cls._resolve_path(path), 100)

    @classmethod
    def load_font(cls, path: str | PathLike[str], font_size: int = 10) -> pygame.font.Font:
        return pygame.font.Font(cls._resolve_path(path), size=font_size)

    @classmethod
    def load_json(cls, path: str | PathLike[str]) -> dict[str, Any]:
        resolved_path = cls._resolve_path(path)
        cache = cls._get_metadata_cache()
        if cache is not None:
            cached = cache.get(resolved_path)
            if cached is not None:
                return dict(cached)
        with resolved_path.open("r") as fp:
            payload = json.load(fp)
        if cache is not None:
            cache.set(resolved_path, payload)
        return dict(payload)


# https://www.pygame.org/wiki/Spritesheet
# I copied this from here it is kinda meh lol
class spritesheet(object):
    def __init__(self, filename: str):
        path = Path(filename)
        if not path.exists():
            raise ValueError(f"'{path}' does not exist.")

        if not path.is_file():
            raise ValueError(f"'{path}' is not a file.")

        with path.open("rb") as f:
            self.sheet = pygame.image.load(f).convert_alpha()
        self._frame_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}
        self._scaled_cache: dict[tuple[int, int, int, int, int, int], pygame.Surface] = {}

    def get_size(self):
        return self.sheet.get_size()

    def image_at(self, rectangle):
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

    def image_at_scaled(self, rectangle, size: tuple[int, int]) -> pygame.Surface:
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
