from __future__ import annotations

from datetime import timedelta
from typing import TypeVar

import reactivex
from reactivex import operators as ops

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
    window_seconds = Configuration.reactivex_stream_replay_window_seconds()
    window = (
        timedelta(seconds=window_seconds)
        if window_seconds is not None and window_seconds > 0
        else None
    )
    if strategy is ReactivexStreamShareStrategy.SHARE:
        return source.pipe(ops.share())
    if strategy is ReactivexStreamShareStrategy.REPLAY_LATEST:
        logger.debug(
            "Sharing %s with replay_latest window=%s",
            stream_name,
            window,
        )
        return source.pipe(
            ops.replay(buffer_size=1, window=window),
            ops.ref_count(),
        )
    if strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER:
        buffer_size = Configuration.reactivex_stream_replay_buffer()
        logger.debug(
            "Sharing %s with replay_buffer=%d window=%s",
            stream_name,
            buffer_size,
            window,
        )
        return source.pipe(
            ops.replay(buffer_size=buffer_size, window=window),
            ops.ref_count(),
        )
    raise ValueError(f"Unknown reactive stream share strategy: {strategy}")
