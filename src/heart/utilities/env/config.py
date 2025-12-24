import os
import platform
import re
from dataclasses import dataclass
from functools import cache

from heart.device.rgb_display.isolated_render import DEFAULT_SOCKET_PATH
from heart.utilities.env.enums import (DeviceLayoutMode, FrameArrayStrategy,
                                       LifeUpdateStrategy,
                                       ReactivexEventBusScheduler,
                                       ReactivexStreamConnectMode,
                                       ReactivexStreamShareStrategy,
                                       RenderMergeStrategy, RenderTileStrategy,
                                       SpritesheetFrameCacheStrategy)

TRUE_FLAG_VALUES = {"true", "1", "yes", "on"}


def _env_flag(env_var: str, *, default: bool = False) -> bool:
    """Return the boolean value of ``env_var`` respecting common true strings."""

    value = os.environ.get(env_var)
    if value is None:
        return default
    return value.strip().lower() in TRUE_FLAG_VALUES


def _env_int(env_var: str, *, default: int, minimum: int | None = None) -> int:
    """Return the integer value of ``env_var`` with optional bounds checking."""

    value = os.environ.get(env_var)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{env_var} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{env_var} must be at least {minimum}")
    return parsed


def _env_optional_int(env_var: str, *, minimum: int | None = None) -> int | None:
    """Return the integer value of ``env_var`` or ``None`` when unset."""

    value = os.environ.get(env_var)
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{env_var} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{env_var} must be at least {minimum}")
    return parsed


@dataclass
class Pi:
    version: int


class Configuration:
    @classmethod
    @cache
    def is_pi(cls) -> bool:
        return platform.system() == "Linux" or _env_flag("ON_PI")

    @classmethod
    def pi(cls) -> Pi | None:
        if not cls.is_pi():
            return None

        with open("/proc/device-tree/model", "rb") as fp:
            raw = fp.read()
            model = raw.decode("ascii", errors="ignore").rstrip("\x00\n")

            # Match “Raspberry Pi X” and capture X
            match = re.search(r"Raspberry Pi (\d+)", model)
            if not match:
                raise ValueError(f"Couldn't parse Pi model from {model!r}")
            return Pi(version=int(match.group(1)))

    @classmethod
    def is_profiling_mode(cls) -> bool:
        return _env_flag("PROFILING_MODE")

    @classmethod
    def is_debug_mode(cls) -> bool:
        return _env_flag("DEBUG_MODE")

    @classmethod
    def is_x11_forward(cls) -> bool:
        return _env_flag("X11_FORWARD")

    @classmethod
    def use_mock_switch(cls) -> bool:
        return _env_flag("MOCK_SWITCH")

    @classmethod
    def use_isolated_renderer(cls) -> bool:
        return _env_flag("USE_ISOLATED_RENDERER")

    @classmethod
    def forward_to_beats_app(cls) -> bool:
        return _env_flag("FORWARD_TO_BEATS_MAP", default=True)

    @classmethod
    def peripheral_configuration(cls) -> str:
        return os.environ.get("PERIPHERAL_CONFIGURATION", "default")

    @classmethod
    def device_layout_mode(cls) -> DeviceLayoutMode:
        raw = os.environ.get("HEART_DEVICE_LAYOUT", "cube").strip().lower()
        try:
            return DeviceLayoutMode(raw)
        except ValueError as exc:
            raise ValueError(
                "HEART_DEVICE_LAYOUT must be 'cube' or 'rectangle'"
            ) from exc

    @classmethod
    def device_layout_columns(cls) -> int:
        return _env_int("HEART_LAYOUT_COLUMNS", default=1, minimum=1)

    @classmethod
    def device_layout_rows(cls) -> int:
        return _env_int("HEART_LAYOUT_ROWS", default=1, minimum=1)

    @classmethod
    def panel_rows(cls) -> int:
        return _env_int("HEART_PANEL_ROWS", default=64, minimum=1)

    @classmethod
    def panel_columns(cls) -> int:
        return _env_int("HEART_PANEL_COLUMNS", default=64, minimum=1)

    @classmethod
    def reactivex_background_max_workers(cls) -> int:
        return _env_int("HEART_RX_BACKGROUND_MAX_WORKERS", default=4, minimum=1)

    @classmethod
    def reactivex_input_max_workers(cls) -> int:
        return _env_int("HEART_RX_INPUT_MAX_WORKERS", default=2, minimum=1)

    @classmethod
    def reactivex_event_bus_scheduler(cls) -> ReactivexEventBusScheduler:
        scheduler = os.environ.get("HEART_RX_EVENT_BUS_SCHEDULER", "inline").strip().lower()
        try:
            return ReactivexEventBusScheduler(scheduler)
        except ValueError as exc:
            raise ValueError(
                "HEART_RX_EVENT_BUS_SCHEDULER must be 'inline', 'background', or 'input'"
            ) from exc

    @classmethod
    def reactivex_stream_share_strategy(cls) -> ReactivexStreamShareStrategy:
        strategy = os.environ.get(
            "HEART_RX_STREAM_SHARE_STRATEGY",
            "replay_latest",
        ).strip().lower()
        try:
            return ReactivexStreamShareStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_RX_STREAM_SHARE_STRATEGY must be 'share', "
                "'share_auto_connect', 'replay_latest', "
                "'replay_latest_auto_connect', 'replay_buffer', or "
                "'replay_buffer_auto_connect'"
            ) from exc

    @classmethod
    def reactivex_stream_coalesce_window_ms(cls) -> int:
        return _env_int("HEART_RX_STREAM_COALESCE_WINDOW_MS", default=0, minimum=0)

    @classmethod
    def reactivex_stream_replay_buffer(cls) -> int:
        return _env_int("HEART_RX_STREAM_REPLAY_BUFFER", default=16, minimum=1)

    @classmethod
    def reactivex_stream_replay_window_ms(cls) -> int | None:
        return _env_optional_int("HEART_RX_STREAM_REPLAY_WINDOW_MS", minimum=1)

    @classmethod
    def reactivex_stream_stats_log_ms(cls) -> int:
        return _env_int("HEART_RX_STREAM_STATS_LOG_MS", default=0, minimum=0)

    @classmethod
    def reactivex_stream_auto_connect_min_subscribers(cls) -> int:
        return _env_int(
            "HEART_RX_STREAM_AUTO_CONNECT_MIN_SUBSCRIBERS",
            default=1,
            minimum=1,
        )

    @classmethod
    def reactivex_stream_refcount_grace_ms(cls) -> int:
        return _env_int("HEART_RX_STREAM_REFCOUNT_GRACE_MS", default=0, minimum=0)

    @classmethod
    def reactivex_stream_refcount_min_subscribers(cls) -> int:
        return _env_int(
            "HEART_RX_STREAM_REFCOUNT_MIN_SUBSCRIBERS",
            default=1,
            minimum=1,
        )

    @classmethod
    def reactivex_stream_connect_mode(cls) -> ReactivexStreamConnectMode:
        mode = os.environ.get("HEART_RX_STREAM_CONNECT_MODE", "lazy").strip().lower()
        try:
            return ReactivexStreamConnectMode(mode)
        except ValueError as exc:
            raise ValueError(
                "HEART_RX_STREAM_CONNECT_MODE must be 'lazy' or 'eager'"
            ) from exc

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
    def hsv_cache_max_size(cls) -> int:
        return _env_int("HEART_HSV_CACHE_MAX_SIZE", default=4096, minimum=0)

    @classmethod
    def hsv_calibration_enabled(cls) -> bool:
        mode = os.environ.get("HEART_HSV_CALIBRATION_MODE")
        if mode is not None:
            normalized = mode.strip().lower()
            if normalized in {"off", "fast", "strict"}:
                return normalized != "off"
            raise ValueError(
                "HEART_HSV_CALIBRATION_MODE must be 'off', 'fast', or 'strict'"
            )
        return _env_flag("HEART_HSV_CALIBRATION", default=True)

    @classmethod
    def hsv_calibration_mode(cls) -> str:
        mode = os.environ.get("HEART_HSV_CALIBRATION_MODE")
        if mode is None:
            return "strict" if cls.hsv_calibration_enabled() else "off"
        normalized = mode.strip().lower()
        if normalized in {"off", "fast", "strict"}:
            return normalized
        raise ValueError(
            "HEART_HSV_CALIBRATION_MODE must be 'off', 'fast', or 'strict'"
        )

    @classmethod
    def render_variant(cls) -> str:
        return os.environ.get("HEART_RENDER_VARIANT", "iterative")

    @classmethod
    def render_parallel_threshold(cls) -> int:
        return _env_int("HEART_RENDER_PARALLEL_THRESHOLD", default=4, minimum=1)

    @classmethod
    def render_executor_max_workers(cls) -> int | None:
        return _env_optional_int("HEART_RENDER_MAX_WORKERS", minimum=1)

    @classmethod
    def render_surface_cache_enabled(cls) -> bool:
        return _env_flag("HEART_RENDER_SURFACE_CACHE", default=True)

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
                "HEART_RENDER_MERGE_STRATEGY must be 'batched' or 'in_place'"
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
