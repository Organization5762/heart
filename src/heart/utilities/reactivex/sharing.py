from __future__ import annotations

from threading import RLock
from typing import Any, TypeVar, cast

import reactivex
from reactivex import operators as ops
from reactivex.disposable import Disposable
from reactivex.scheduler import TimeoutScheduler

from heart.utilities.env import ReactivexStreamConnectMode, ReactivexStreamShareStrategy
from heart.utilities.logging import get_logger
from heart.utilities.reactivex.coalescing import coalesce_latest
from heart.utilities.reactivex.instrumentation import instrument_stream
from heart.utilities.reactivex.settings import StreamShareSettings
from heart.utilities.reactivex.types import ConnectableStream

logger = get_logger(__name__)

T = TypeVar("T")
_REPLAY_SCHEDULER = TimeoutScheduler()
_GRACE_SCHEDULER = TimeoutScheduler()


def _share_with_refcount_grace(
    connectable: ConnectableStream[T],
    *,
    grace_ms: int,
    min_subscribers: int,
    connect_mode: ReactivexStreamConnectMode,
    stream_name: str,
) -> reactivex.Observable[T]:
    lock = RLock()
    connection: Any | None = None
    disconnect_timer: Any | None = None
    subscriber_count = 0

    def _disconnect() -> None:
        nonlocal connection, disconnect_timer, subscriber_count
        with lock:
            disconnect_timer = None
            if connection is None or subscriber_count >= min_subscribers:
                return
            logger.debug("Disconnecting %s after refcount grace window", stream_name)
            connection.dispose()
            connection = None

    def _subscribe(observer: Any, scheduler: Any = None) -> Disposable:
        nonlocal connection, disconnect_timer, subscriber_count
        with lock:
            subscriber_count += 1
            if disconnect_timer is not None:
                disconnect_timer.dispose()
                disconnect_timer = None
            if (
                connection is None
                and connect_mode is ReactivexStreamConnectMode.EAGER
                and subscriber_count >= min_subscribers
            ):
                logger.debug(
                    "Connecting %s with refcount grace (grace_ms=%d, mode=%s, min=%d)",
                    stream_name,
                    grace_ms,
                    connect_mode,
                    min_subscribers,
                )
                connection = connectable.connect()

        subscription = connectable.subscribe(observer)
        if connect_mode is ReactivexStreamConnectMode.LAZY:
            with lock:
                if connection is None and subscriber_count >= min_subscribers:
                    logger.debug(
                        "Connecting %s with refcount grace (grace_ms=%d, mode=%s, min=%d)",
                        stream_name,
                        grace_ms,
                        connect_mode,
                        min_subscribers,
                    )
                    connection = connectable.connect()

        def _dispose() -> None:
            nonlocal subscriber_count, disconnect_timer
            subscription.dispose()
            with lock:
                subscriber_count -= 1
                if subscriber_count >= min_subscribers or connection is None:
                    return
                if grace_ms <= 0:
                    _disconnect()
                    return
                logger.debug(
                    "Scheduling disconnect for %s in %dms (min=%d)",
                    stream_name,
                    grace_ms,
                    min_subscribers,
                )
                if disconnect_timer is not None:
                    disconnect_timer.dispose()
                    disconnect_timer = None
                disconnect_timer = _GRACE_SCHEDULER.schedule_relative(
                    grace_ms / 1000,
                    lambda *_: _disconnect(),
                )

        return Disposable(_dispose)

    return reactivex.create(_subscribe)


def share_stream(
    source: reactivex.Observable[T],
    *,
    stream_name: str,
) -> reactivex.Observable[T]:
    """Share a stream using the configured strategy."""
    settings = StreamShareSettings.from_environment()
    strategy = settings.strategy
    coalesce_window_ms = settings.coalesce_window_ms
    stats_log_ms = settings.stats_log_ms
    replay_window_ms = settings.replay_window_ms
    auto_connect_min_subscribers = settings.auto_connect_min_subscribers
    refcount_min_subscribers = settings.refcount_min_subscribers
    refcount_grace_ms = settings.refcount_grace_ms
    connect_mode = settings.connect_mode
    replay_window_seconds = (
        None if replay_window_ms is None else replay_window_ms / 1000
    )
    source = coalesce_latest(
        source,
        window_ms=coalesce_window_ms,
        stream_name=stream_name,
    )

    def _replay(buffer_size: int) -> ConnectableStream[T]:
        if replay_window_seconds is None:
            return cast(
                ConnectableStream[T],
                source.pipe(ops.replay(buffer_size=buffer_size)),
            )
        return cast(
            ConnectableStream[T],
            source.pipe(
                ops.replay(
                    buffer_size=buffer_size,
                    window=replay_window_seconds,
                    scheduler=_REPLAY_SCHEDULER,
                )
            ),
        )

    if strategy is ReactivexStreamShareStrategy.SHARE:
        logger.debug(
            "Sharing %s with share (refcount_grace_ms=%d, min=%d)",
            stream_name,
            refcount_grace_ms,
            refcount_min_subscribers,
        )
        if refcount_grace_ms > 0 or refcount_min_subscribers > 1:
            result = _share_with_refcount_grace(
                cast(ConnectableStream[T], source.pipe(ops.publish())),
                grace_ms=refcount_grace_ms,
                min_subscribers=refcount_min_subscribers,
                connect_mode=connect_mode,
                stream_name=stream_name,
            )
        else:
            result = source.pipe(ops.share())
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=stats_log_ms,
        )
    if strategy is ReactivexStreamShareStrategy.SHARE_AUTO_CONNECT:
        logger.debug(
            "Sharing %s with share_auto_connect (min_subscribers=%d)",
            stream_name,
            auto_connect_min_subscribers,
        )
        result = source.pipe(ops.publish()).auto_connect(auto_connect_min_subscribers)
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=stats_log_ms,
        )
    if strategy is ReactivexStreamShareStrategy.REPLAY_LATEST:
        logger.debug(
            "Sharing %s with replay_latest (window_ms=%s, refcount_grace_ms=%d, min=%d)",
            stream_name,
            replay_window_ms,
            refcount_grace_ms,
            refcount_min_subscribers,
        )
        replayed = _replay(1)
        if refcount_grace_ms > 0 or refcount_min_subscribers > 1:
            result = _share_with_refcount_grace(
                replayed,
                grace_ms=refcount_grace_ms,
                min_subscribers=refcount_min_subscribers,
                connect_mode=connect_mode,
                stream_name=stream_name,
            )
        else:
            result = replayed.pipe(ops.ref_count())
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=stats_log_ms,
        )
    if strategy is ReactivexStreamShareStrategy.REPLAY_LATEST_AUTO_CONNECT:
        logger.debug(
            "Sharing %s with replay_latest_auto_connect "
            "(window_ms=%s, min_subscribers=%d)",
            stream_name,
            replay_window_ms,
            auto_connect_min_subscribers,
        )
        result = _replay(1).auto_connect(auto_connect_min_subscribers)
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=stats_log_ms,
        )
    if strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER:
        buffer_size = settings.replay_buffer()
        logger.debug(
            "Sharing %s with replay_buffer=%d (window_ms=%s, refcount_grace_ms=%d, min=%d)",
            stream_name,
            buffer_size,
            replay_window_ms,
            refcount_grace_ms,
            refcount_min_subscribers,
        )
        replayed = _replay(buffer_size)
        if refcount_grace_ms > 0 or refcount_min_subscribers > 1:
            result = _share_with_refcount_grace(
                replayed,
                grace_ms=refcount_grace_ms,
                min_subscribers=refcount_min_subscribers,
                connect_mode=connect_mode,
                stream_name=stream_name,
            )
        else:
            result = replayed.pipe(ops.ref_count())
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=stats_log_ms,
        )
    if strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER_AUTO_CONNECT:
        buffer_size = settings.replay_buffer()
        logger.debug(
            "Sharing %s with replay_buffer_auto_connect=%d "
            "(window_ms=%s, min_subscribers=%d)",
            stream_name,
            buffer_size,
            replay_window_ms,
            auto_connect_min_subscribers,
        )
        result = _replay(buffer_size).auto_connect(auto_connect_min_subscribers)
        return instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=stats_log_ms,
        )
    raise ValueError(f"Unknown reactive stream share strategy: {strategy}")
