import os

from heart.utilities.env.enums import (AssetCacheStrategy,
                                       SpritesheetFrameCacheStrategy)


class AssetsConfiguration:
    @classmethod
    def asset_cache_strategy(cls) -> AssetCacheStrategy:
        strategy = os.environ.get("HEART_ASSET_CACHE_STRATEGY", "all").strip().lower()
        try:
            return AssetCacheStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_ASSET_CACHE_STRATEGY must be 'none', 'metadata', 'images', 'spritesheets', or 'all'"
            ) from exc

    @classmethod
    def asset_cache_max_entries(cls) -> int:
        value = os.environ.get("HEART_ASSET_CACHE_MAX_ENTRIES", "64").strip()
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(
                "HEART_ASSET_CACHE_MAX_ENTRIES must be an integer >= 0"
            ) from exc
        if parsed < 0:
            raise ValueError(
                "HEART_ASSET_CACHE_MAX_ENTRIES must be an integer >= 0"
            )
        return parsed

    @classmethod
    def spritesheet_frame_cache_strategy(cls) -> SpritesheetFrameCacheStrategy:
        strategy = os.environ.get(
            "HEART_SPRITESHEET_FRAME_CACHE_STRATEGY", "scaled"
        ).strip().lower()
        try:
            return SpritesheetFrameCacheStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_SPRITESHEET_FRAME_CACHE_STRATEGY must be 'none', 'frames', or 'scaled'"
            ) from exc
