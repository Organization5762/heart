from __future__ import annotations

from typing import TypeVar

import reactivex
from reactivex import operators as ops
from reactivex.scheduler import TimeoutScheduler

from heart.utilities.env import Configuration, ReactivexStreamShareStrategy
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def share_stream(
    source: reactivex.Observable[T],
    *,
    stream_name: str,
) -> reactivex.Observable[T]:
    """Share a stream using the configured strategy."""

    strategy = Configuration.reactivex_stream_share_strategy()
    replay_window_ms = Configuration.reactivex_stream_replay_window_ms()
    auto_connect_min_subscribers = (
        Configuration.reactivex_stream_auto_connect_min_subscribers()
    )
    replay_window_seconds = (
        None if replay_window_ms is None else replay_window_ms / 1000
    )

    def _replay(buffer_size: int) -> reactivex.Observable[T]:
        if replay_window_seconds is None:
            return source.pipe(ops.replay(buffer_size=buffer_size))
        return source.pipe(
            ops.replay(
                buffer_size=buffer_size,
                window=replay_window_seconds,
                scheduler=TimeoutScheduler(),
            )
        )

    if strategy is ReactivexStreamShareStrategy.SHARE:
        logger.debug("Sharing %s with share", stream_name)
        return source.pipe(ops.share())
    if strategy is ReactivexStreamShareStrategy.REPLAY_LATEST:
        logger.debug(
            "Sharing %s with replay_latest (window_ms=%s)",
            stream_name,
            replay_window_ms,
        )
        return _replay(1).pipe(ops.ref_count())
    if strategy is ReactivexStreamShareStrategy.REPLAY_LATEST_AUTO_CONNECT:
        logger.debug(
            "Sharing %s with replay_latest_auto_connect "
            "(window_ms=%s, min_subscribers=%d)",
            stream_name,
            replay_window_ms,
            auto_connect_min_subscribers,
        )
        return _replay(1).auto_connect(auto_connect_min_subscribers)
    if strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER:
        buffer_size = Configuration.reactivex_stream_replay_buffer()
        logger.debug(
            "Sharing %s with replay_buffer=%d (window_ms=%s)",
            stream_name,
            buffer_size,
            replay_window_ms,
        )
        return _replay(buffer_size).pipe(ops.ref_count())
    if strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER_AUTO_CONNECT:
        buffer_size = Configuration.reactivex_stream_replay_buffer()
        logger.debug(
            "Sharing %s with replay_buffer_auto_connect=%d "
            "(window_ms=%s, min_subscribers=%d)",
            stream_name,
            buffer_size,
            replay_window_ms,
            auto_connect_min_subscribers,
        )
        return _replay(buffer_size).auto_connect(auto_connect_min_subscribers)
    raise ValueError(f"Unknown reactive stream share strategy: {strategy}")
