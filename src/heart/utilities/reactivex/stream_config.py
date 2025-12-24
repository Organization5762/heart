from __future__ import annotations

from dataclasses import dataclass

from heart.utilities.env import (Configuration, ReactivexStreamConnectMode,
                                 ReactivexStreamShareStrategy)


@dataclass(frozen=True)
class StreamShareSettings:
    """Resolved configuration for reactive stream sharing."""

    strategy: ReactivexStreamShareStrategy
    coalesce_window_ms: int
    stats_log_ms: int
    replay_window_ms: int | None
    auto_connect_min_subscribers: int
    refcount_min_subscribers: int
    refcount_grace_ms: int
    connect_mode: ReactivexStreamConnectMode
    replay_buffer_size: int

    @classmethod
    def from_environment(cls) -> StreamShareSettings:
        return cls(
            strategy=Configuration.reactivex_stream_share_strategy(),
            coalesce_window_ms=Configuration.reactivex_stream_coalesce_window_ms(),
            stats_log_ms=Configuration.reactivex_stream_stats_log_ms(),
            replay_window_ms=Configuration.reactivex_stream_replay_window_ms(),
            auto_connect_min_subscribers=(
                Configuration.reactivex_stream_auto_connect_min_subscribers()
            ),
            refcount_min_subscribers=(
                Configuration.reactivex_stream_refcount_min_subscribers()
            ),
            refcount_grace_ms=Configuration.reactivex_stream_refcount_grace_ms(),
            connect_mode=Configuration.reactivex_stream_connect_mode(),
            replay_buffer_size=Configuration.reactivex_stream_replay_buffer(),
        )
