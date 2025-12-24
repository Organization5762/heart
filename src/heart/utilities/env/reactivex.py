import os

from heart.utilities.env.enums import (ReactivexEventBusScheduler,
                                       ReactivexStreamConnectMode,
                                       ReactivexStreamShareStrategy)
from heart.utilities.env.parsing import _env_int, _env_optional_int


class ReactivexConfiguration:
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
