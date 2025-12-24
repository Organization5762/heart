import os

from heart.utilities.env.enums import SpritesheetFrameCacheStrategy


class AssetsConfiguration:
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
