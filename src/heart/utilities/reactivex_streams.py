from __future__ import annotations

from typing import TypeVar

import reactivex
from reactivex import operators as ops

from heart.utilities.env import Configuration
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
    if strategy == "share":
        return source.pipe(ops.share())
    if strategy == "replay_latest":
        logger.debug("Sharing %s with replay_latest", stream_name)
        return source.pipe(ops.replay(buffer_size=1), ops.ref_count())
    if strategy == "replay_buffer":
        buffer_size = Configuration.reactivex_stream_replay_buffer()
        logger.debug("Sharing %s with replay_buffer=%d", stream_name, buffer_size)
        return source.pipe(ops.replay(buffer_size=buffer_size), ops.ref_count())
    raise ValueError(f"Unknown reactive stream share strategy: {strategy}")
