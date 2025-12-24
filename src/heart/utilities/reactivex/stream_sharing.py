from __future__ import annotations

from typing import TypeVar, cast

import reactivex
from reactivex import operators as ops

from heart.utilities.env import ReactivexStreamShareStrategy
from heart.utilities.logging import get_logger
from heart.utilities.reactivex.stream_config import StreamShareSettings
from heart.utilities.reactivex.stream_ops import (ConnectableStream,
                                                  coalesce_latest,
                                                  instrument_stream,
                                                  replay_stream,
                                                  share_with_refcount_grace)

logger = get_logger(__name__)

T = TypeVar("T")


def share_stream(
    source: reactivex.Observable[T],
    *,
    stream_name: str,
) -> reactivex.Observable[T]:
    """Share a stream using the configured strategy."""

    settings = StreamShareSettings.from_environment()
    source = coalesce_latest(
        source,
        window_ms=settings.coalesce_window_ms,
        stream_name=stream_name,
    )

    if settings.strategy is ReactivexStreamShareStrategy.SHARE:
        logger.debug(
            "Sharing %s with share (refcount_grace_ms=%d, min=%d)",
            stream_name,
            settings.refcount_grace_ms,
            settings.refcount_min_subscribers,
        )
        if settings.refcount_grace_ms > 0 or settings.refcount_min_subscribers > 1:
            result = share_with_refcount_grace(
                cast(ConnectableStream[T], source.pipe(ops.publish())),
                grace_ms=settings.refcount_grace_ms,
                min_subscribers=settings.refcount_min_subscribers,
                connect_mode=settings.connect_mode,
                stream_name=stream_name,
            )
        else:
            result = source.pipe(ops.share())
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=settings.stats_log_ms,
        )
    if settings.strategy is ReactivexStreamShareStrategy.SHARE_AUTO_CONNECT:
        logger.debug(
            "Sharing %s with share_auto_connect (min_subscribers=%d)",
            stream_name,
            settings.auto_connect_min_subscribers,
        )
        result = source.pipe(ops.publish()).auto_connect(
            settings.auto_connect_min_subscribers
        )
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=settings.stats_log_ms,
        )
    if settings.strategy is ReactivexStreamShareStrategy.REPLAY_LATEST:
        logger.debug(
            "Sharing %s with replay_latest (window_ms=%s, refcount_grace_ms=%d, min=%d)",
            stream_name,
            settings.replay_window_ms,
            settings.refcount_grace_ms,
            settings.refcount_min_subscribers,
        )
        replayed = replay_stream(
            source,
            buffer_size=1,
            window_ms=settings.replay_window_ms,
        )
        if settings.refcount_grace_ms > 0 or settings.refcount_min_subscribers > 1:
            result = share_with_refcount_grace(
                replayed,
                grace_ms=settings.refcount_grace_ms,
                min_subscribers=settings.refcount_min_subscribers,
                connect_mode=settings.connect_mode,
                stream_name=stream_name,
            )
        else:
            result = replayed.pipe(ops.ref_count())
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=settings.stats_log_ms,
        )
    if settings.strategy is ReactivexStreamShareStrategy.REPLAY_LATEST_AUTO_CONNECT:
        logger.debug(
            "Sharing %s with replay_latest_auto_connect "
            "(window_ms=%s, min_subscribers=%d)",
            stream_name,
            settings.replay_window_ms,
            settings.auto_connect_min_subscribers,
        )
        result = replay_stream(
            source,
            buffer_size=1,
            window_ms=settings.replay_window_ms,
        ).auto_connect(settings.auto_connect_min_subscribers)
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=settings.stats_log_ms,
        )
    if settings.strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER:
        logger.debug(
            "Sharing %s with replay_buffer=%d (window_ms=%s, refcount_grace_ms=%d, min=%d)",
            stream_name,
            settings.replay_buffer_size,
            settings.replay_window_ms,
            settings.refcount_grace_ms,
            settings.refcount_min_subscribers,
        )
        replayed = replay_stream(
            source,
            buffer_size=settings.replay_buffer_size,
            window_ms=settings.replay_window_ms,
        )
        if settings.refcount_grace_ms > 0 or settings.refcount_min_subscribers > 1:
            result = share_with_refcount_grace(
                replayed,
                grace_ms=settings.refcount_grace_ms,
                min_subscribers=settings.refcount_min_subscribers,
                connect_mode=settings.connect_mode,
                stream_name=stream_name,
            )
        else:
            result = replayed.pipe(ops.ref_count())
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=settings.stats_log_ms,
        )
    if settings.strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER_AUTO_CONNECT:
        logger.debug(
            "Sharing %s with replay_buffer_auto_connect=%d "
            "(window_ms=%s, min_subscribers=%d)",
            stream_name,
            settings.replay_buffer_size,
            settings.replay_window_ms,
            settings.auto_connect_min_subscribers,
        )
        result = replay_stream(
            source,
            buffer_size=settings.replay_buffer_size,
            window_ms=settings.replay_window_ms,
        ).auto_connect(settings.auto_connect_min_subscribers)
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=settings.stats_log_ms,
        )
    raise ValueError(
        "Unknown reactive stream share strategy: "
        f"{settings.strategy}"
    )
