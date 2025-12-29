import os

from heart.device.rgb_display.constants import DEFAULT_SOCKET_PATH
from heart.utilities.env.enums import (FrameArrayStrategy, FrameExportStrategy,
                                       IsolatedRendererAckStrategy,
                                       IsolatedRendererDedupStrategy,
                                       LifeRuleStrategy, LifeUpdateStrategy,
                                       RendererTimingStrategy,
                                       RenderLoopPacingStrategy,
                                       RenderMergeStrategy,
                                       RenderPlanSignatureStrategy,
                                       RenderTileStrategy)
from heart.utilities.env.parsing import (_env_flag, _env_float, _env_int,
                                         _env_optional_int)

DEFAULT_RENDER_PLAN_REFRESH_MS = 100
DEFAULT_RENDER_TIMING_EMA_ALPHA = 0.2
DEFAULT_RENDER_TIMING_STRATEGY = RendererTimingStrategy.EMA
DEFAULT_RENDER_LOOP_PACING_STRATEGY = RenderLoopPacingStrategy.OFF
DEFAULT_RENDER_LOOP_PACING_MIN_INTERVAL_MS = 0.0
DEFAULT_RENDER_LOOP_PACING_UTILIZATION = 0.9
DEFAULT_RENDER_PLAN_SIGNATURE_STRATEGY = RenderPlanSignatureStrategy.INSTANCE


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
    def isolated_renderer_ack_strategy(cls) -> IsolatedRendererAckStrategy:
        strategy = os.environ.get(
            "HEART_ISOLATED_RENDERER_ACK_STRATEGY", "always"
        ).strip().lower()
        try:
            return IsolatedRendererAckStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_ISOLATED_RENDERER_ACK_STRATEGY must be 'always' or 'never'"
            ) from exc

    @classmethod
    def isolated_renderer_ack_timeout_ms(cls) -> int:
        return _env_int(
            "HEART_ISOLATED_RENDERER_ACK_TIMEOUT_MS", default=1000, minimum=0
        )

    @classmethod
    def isolated_renderer_dedup_strategy(cls) -> IsolatedRendererDedupStrategy:
        strategy = os.environ.get(
            "HEART_ISOLATED_RENDERER_DEDUP_STRATEGY", "source"
        ).strip().lower()
        try:
            return IsolatedRendererDedupStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_ISOLATED_RENDERER_DEDUP_STRATEGY must be 'none', 'source', or 'payload'"
            ) from exc

    @classmethod
    def render_variant(cls) -> str:
        return os.environ.get("HEART_RENDER_VARIANT", "iterative")

    @classmethod
    def render_plan_refresh_ms(cls) -> int:
        return _env_int(
            "HEART_RENDER_PLAN_REFRESH_MS",
            default=DEFAULT_RENDER_PLAN_REFRESH_MS,
            minimum=0,
        )

    @classmethod
    def render_plan_signature_strategy(cls) -> RenderPlanSignatureStrategy:
        strategy = os.environ.get(
            "HEART_RENDER_PLAN_SIGNATURE_STRATEGY",
            DEFAULT_RENDER_PLAN_SIGNATURE_STRATEGY.value,
        ).strip().lower()
        try:
            return RenderPlanSignatureStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_RENDER_PLAN_SIGNATURE_STRATEGY must be 'instance' or 'type'"
            ) from exc

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
        return _env_flag("HEART_RENDER_SURFACE_CACHE", default=False)

    @classmethod
    def render_screen_cache_enabled(cls) -> bool:
        return _env_flag("HEART_RENDER_SCREEN_CACHE", default=False)

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
            "HEART_RENDER_MERGE_STRATEGY", "adaptive"
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
    def render_timing_strategy(cls) -> RendererTimingStrategy:
        strategy = os.environ.get(
            "HEART_RENDER_TIMING_STRATEGY",
            DEFAULT_RENDER_TIMING_STRATEGY.value,
        ).strip().lower()
        try:
            return RendererTimingStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_RENDER_TIMING_STRATEGY must be 'cumulative' or 'ema'"
            ) from exc

    @classmethod
    def render_timing_ema_alpha(cls) -> float:
        alpha = _env_float(
            "HEART_RENDER_TIMING_EMA_ALPHA",
            default=DEFAULT_RENDER_TIMING_EMA_ALPHA,
            minimum=0.0,
            maximum=1.0,
        )
        if alpha <= 0.0:
            raise ValueError(
                "HEART_RENDER_TIMING_EMA_ALPHA must be greater than 0 and at most 1"
            )
        return alpha

    @classmethod
    def render_loop_pacing_strategy(cls) -> RenderLoopPacingStrategy:
        strategy = os.environ.get(
            "HEART_RENDER_LOOP_PACING_STRATEGY",
            DEFAULT_RENDER_LOOP_PACING_STRATEGY.value,
        ).strip().lower()
        try:
            return RenderLoopPacingStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_RENDER_LOOP_PACING_STRATEGY must be 'off' or 'adaptive'"
            ) from exc

    @classmethod
    def render_loop_pacing_min_interval_ms(cls) -> float:
        return _env_float(
            "HEART_RENDER_LOOP_PACING_MIN_INTERVAL_MS",
            default=DEFAULT_RENDER_LOOP_PACING_MIN_INTERVAL_MS,
            minimum=0.0,
        )

    @classmethod
    def render_loop_pacing_utilization(cls) -> float:
        utilization = _env_float(
            "HEART_RENDER_LOOP_PACING_UTILIZATION",
            default=DEFAULT_RENDER_LOOP_PACING_UTILIZATION,
            minimum=0.0,
            maximum=1.0,
        )
        if utilization <= 0.0:
            raise ValueError(
                "HEART_RENDER_LOOP_PACING_UTILIZATION must be greater than 0 and at most 1"
            )
        return utilization

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
            "HEART_FRAME_EXPORT_STRATEGY", "array"
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

    @classmethod
    def life_rule_strategy(cls) -> LifeRuleStrategy:
        strategy = os.environ.get("HEART_LIFE_RULE_STRATEGY", "auto").strip().lower()
        try:
            return LifeRuleStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_LIFE_RULE_STRATEGY must be 'auto', 'direct', or 'table'"
            ) from exc

    @classmethod
    def life_random_seed(cls) -> int | None:
        return _env_optional_int("HEART_LIFE_RANDOM_SEED", minimum=0)
