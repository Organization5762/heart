import os

from heart.device.rgb_display.isolated_render import DEFAULT_SOCKET_PATH
from heart.utilities.env.enums import (FrameArrayStrategy, FrameExportStrategy,
                                       LifeUpdateStrategy, RenderMergeStrategy,
                                       RenderTileStrategy)
from heart.utilities.env.parsing import _env_flag, _env_int, _env_optional_int


class RenderingConfiguration:
    @classmethod
    def isolated_renderer_socket(cls) -> str | None:
        socket_path = os.environ.get("ISOLATED_RENDER_SOCKET")
        if socket_path == "":
            return None
        if socket_path is not None:
            return socket_path
        if cls.isolated_renderer_tcp_address() is not None:
            return None
        return DEFAULT_SOCKET_PATH

    @classmethod
    def isolated_renderer_tcp_address(cls) -> tuple[str, int] | None:
        host = os.environ.get("ISOLATED_RENDER_HOST")
        port = os.environ.get("ISOLATED_RENDER_PORT")
        if host and port:
            try:
                return host, int(port)
            except ValueError:
                raise ValueError(
                    "ISOLATED_RENDER_PORT must be an integer when ISOLATED_RENDER_HOST is set"
                )
        if host or port:
            raise ValueError(
                "Both ISOLATED_RENDER_HOST and ISOLATED_RENDER_PORT must be set together"
            )
        return None

    @classmethod
    def render_variant(cls) -> str:
        return os.environ.get("HEART_RENDER_VARIANT", "iterative")

    @classmethod
    def render_parallel_threshold(cls) -> int:
        return _env_int("HEART_RENDER_PARALLEL_THRESHOLD", default=4, minimum=1)

    @classmethod
    def render_parallel_cost_threshold_ms(cls) -> int:
        return _env_int(
            "HEART_RENDER_PARALLEL_COST_THRESHOLD_MS", default=12, minimum=0
        )

    @classmethod
    def render_executor_max_workers(cls) -> int | None:
        return _env_optional_int("HEART_RENDER_MAX_WORKERS", minimum=1)

    @classmethod
    def render_surface_cache_enabled(cls) -> bool:
        return _env_flag("HEART_RENDER_SURFACE_CACHE", default=True)

    @classmethod
    def render_screen_cache_enabled(cls) -> bool:
        return _env_flag("HEART_RENDER_SCREEN_CACHE", default=True)

    @classmethod
    def render_tile_strategy(cls) -> RenderTileStrategy:
        strategy = os.environ.get("HEART_RENDER_TILE_STRATEGY", "blits").strip().lower()
        try:
            return RenderTileStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_RENDER_TILE_STRATEGY must be 'blits' or 'loop'"
            ) from exc

    @classmethod
    def render_merge_strategy(cls) -> RenderMergeStrategy:
        strategy = os.environ.get(
            "HEART_RENDER_MERGE_STRATEGY", "batched"
        ).strip().lower()
        try:
            return RenderMergeStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_RENDER_MERGE_STRATEGY must be 'batched', 'in_place', or 'adaptive'"
            ) from exc

    @classmethod
    def render_merge_cost_threshold_ms(cls) -> int:
        return _env_int("HEART_RENDER_MERGE_COST_THRESHOLD_MS", default=6, minimum=0)

    @classmethod
    def render_merge_surface_threshold(cls) -> int:
        return _env_int("HEART_RENDER_MERGE_SURFACE_THRESHOLD", default=3, minimum=1)

    @classmethod
    def frame_array_strategy(cls) -> FrameArrayStrategy:
        strategy = os.environ.get("HEART_FRAME_ARRAY_STRATEGY", "copy").strip().lower()
        try:
            return FrameArrayStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_FRAME_ARRAY_STRATEGY must be 'copy' or 'view'"
            ) from exc

    @classmethod
    def frame_export_strategy(cls) -> FrameExportStrategy:
        strategy = os.environ.get(
            "HEART_FRAME_EXPORT_STRATEGY", "buffer"
        ).strip().lower()
        try:
            return FrameExportStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_FRAME_EXPORT_STRATEGY must be 'buffer' or 'array'"
            ) from exc

    @classmethod
    def life_update_strategy(cls) -> LifeUpdateStrategy:
        strategy = os.environ.get("HEART_LIFE_UPDATE_STRATEGY", "auto").strip().lower()
        try:
            return LifeUpdateStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_LIFE_UPDATE_STRATEGY must be 'auto', 'convolve', 'pad', or 'shifted'"
            ) from exc

    @classmethod
    def life_convolve_threshold(cls) -> int:
        return _env_int("HEART_LIFE_CONVOLVE_THRESHOLD", default=0, minimum=0)
