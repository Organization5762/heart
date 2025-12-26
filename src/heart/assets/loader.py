import json
from os import PathLike
from pathlib import Path
from typing import Any

import pygame

from heart.assets.animation import Animation
from heart.assets.cache import AssetCache
from heart.assets.spritesheet import Spritesheet
from heart.utilities.env import AssetCacheStrategy, Configuration

DEFAULT_FONT_SIZE = 10


class Loader:
    _image_cache: AssetCache[Path, pygame.Surface] | None = None
    _spritesheet_cache: AssetCache[Path, Spritesheet] | None = None
    _metadata_cache: AssetCache[Path, dict[str, Any]] | None = None

    @classmethod
    def _resolve_cache_strategy(cls) -> AssetCacheStrategy:
        return Configuration.asset_cache_strategy()

    @classmethod
    def _cache_max_entries(cls) -> int:
        return Configuration.asset_cache_max_entries()

    @classmethod
    def _get_spritesheet_cache(cls) -> AssetCache[Path, Spritesheet] | None:
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
    def load_spirtesheet(cls, path: str | PathLike[str]) -> Spritesheet:
        resolved_path = cls._resolve_path(path)
        cache = cls._get_spritesheet_cache()
        if cache is not None:
            cached = cache.get(resolved_path)
            if cached is not None:
                return cached
        loaded = Spritesheet(resolved_path)
        if cache is not None:
            cache.set(resolved_path, loaded)
        return loaded

    @classmethod
    def load_animation(cls, path: str | PathLike[str]) -> Animation:
        return Animation(cls.load_spirtesheet(path), 100)

    @classmethod
    def load_font(
        cls, path: str | PathLike[str], font_size: int = DEFAULT_FONT_SIZE
    ) -> pygame.font.Font:
        return pygame.font.Font(cls._resolve_path(path), size=font_size)

    @classmethod
    def load_json(cls, path: str | PathLike[str]) -> dict[str, Any]:
        resolved_path = cls._resolve_path(path)
        cache = cls._get_metadata_cache()
        if cache is not None:
            cached = cache.get(resolved_path)
            if cached is not None:
                return dict(cached)
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        if cache is not None:
            cache.set(resolved_path, payload)
        return dict(payload)
