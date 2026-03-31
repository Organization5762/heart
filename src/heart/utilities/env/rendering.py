import os

from heart.device.rgb_display.constants import DEFAULT_SOCKET_PATH
from heart.utilities.env.enums import (FrameArrayStrategy, FrameExportStrategy,
                                       IsolatedRendererAckStrategy,
                                       IsolatedRendererDedupStrategy,
                                       LifeRuleStrategy, LifeUpdateStrategy,
                                       RenderTileStrategy)
from heart.utilities.env.parsing import _env_flag, _env_int, _env_optional_int

DEFAULT_RENDER_CRASH_ON_ERROR = False


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
    def render_crash_on_error(cls) -> bool:
        return _env_flag(
            "HEART_RENDER_CRASH_ON_ERROR",
            default=DEFAULT_RENDER_CRASH_ON_ERROR,
        )

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
