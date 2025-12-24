from __future__ import annotations

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
    auto_connect_subscribers = Configuration.reactivex_stream_auto_connect_subscribers()
    if strategy is ReactivexStreamShareStrategy.SHARE:
        logger.debug("Sharing %s with share", stream_name)
        return source.pipe(ops.share())
    if strategy is ReactivexStreamShareStrategy.SHARE_AUTO_CONNECT:
        logger.debug(
            "Sharing %s with share_auto_connect subscribers=%d",
            stream_name,
            auto_connect_subscribers,
        )
        return source.pipe(ops.publish()).auto_connect(auto_connect_subscribers)
    if strategy is ReactivexStreamShareStrategy.REPLAY_LATEST:
        logger.debug("Sharing %s with replay_latest", stream_name)
        return source.pipe(ops.replay(buffer_size=1), ops.ref_count())
    if strategy is ReactivexStreamShareStrategy.REPLAY_LATEST_AUTO_CONNECT:
        logger.debug(
            "Sharing %s with replay_latest_auto_connect subscribers=%d",
            stream_name,
            auto_connect_subscribers,
        )
        return source.pipe(ops.replay(buffer_size=1)).auto_connect(
            auto_connect_subscribers
        )
    if strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER:
        buffer_size = Configuration.reactivex_stream_replay_buffer()
        logger.debug("Sharing %s with replay_buffer=%d", stream_name, buffer_size)
        return source.pipe(ops.replay(buffer_size=buffer_size), ops.ref_count())
    if strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER_AUTO_CONNECT:
        buffer_size = Configuration.reactivex_stream_replay_buffer()
        logger.debug(
            "Sharing %s with replay_buffer_auto_connect=%d subscribers=%d",
            stream_name,
            buffer_size,
            auto_connect_subscribers,
        )
        return source.pipe(ops.replay(buffer_size=buffer_size)).auto_connect(
            auto_connect_subscribers
        )
    raise ValueError(f"Unknown reactive stream share strategy: {strategy}")
