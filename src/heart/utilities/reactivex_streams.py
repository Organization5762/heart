from __future__ import annotations

from threading import RLock
from typing import Any, Protocol, TypeVar, cast

import reactivex
from reactivex import operators as ops
from reactivex.disposable import Disposable
from reactivex.scheduler import TimeoutScheduler

from heart.utilities.env import (Configuration, ReactivexStreamCoalesceMode,
                                 ReactivexStreamConnectMode,
                                 ReactivexStreamShareStrategy)
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
_REPLAY_SCHEDULER = TimeoutScheduler()
_GRACE_SCHEDULER = TimeoutScheduler()
_COALESCE_SCHEDULER = TimeoutScheduler()
_STATS_SCHEDULER = TimeoutScheduler()
_NO_PENDING: Any = object()


class ConnectableStream(Protocol[T_co]):
    def connect(self, scheduler: Any = None) -> Disposable: ...

    def subscribe(self, observer: Any = None, scheduler: Any = None) -> Disposable: ...

    def pipe(self, *operators: Any) -> reactivex.Observable[T_co]: ...

    def auto_connect(
        self, subscriber_count: int = 1
    ) -> reactivex.Observable[T_co]: ...


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

        subscription = connectable.subscribe(observer, scheduler=scheduler)
        if connect_mode is ReactivexStreamConnectMode.LAZY:
            with lock:
                if (
                    connection is None
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
                disconnect_timer = _GRACE_SCHEDULER.schedule_relative(
                    grace_ms / 1000,
                    lambda *_: _disconnect(),
                )

        return Disposable(_dispose)

    return reactivex.create(_subscribe)


def _coalesce_stream(
    source: reactivex.Observable[T],
    *,
    window_ms: int,
    mode: ReactivexStreamCoalesceMode,
    stream_name: str,
) -> reactivex.Observable[T]:
    if window_ms <= 0:
        return source

    def _subscribe(observer: Any, scheduler: Any = None) -> Disposable:
        lock = RLock()
        pending: Any = _NO_PENDING
        timer: Any | None = None

        def _flush() -> None:
            nonlocal pending, timer
            with lock:
                value = pending
                pending = _NO_PENDING
                timer = None
            if value is _NO_PENDING:
                return
            observer.on_next(value)

        def _schedule_flush() -> None:
            nonlocal timer
            if timer is not None:
                return
            timer = _COALESCE_SCHEDULER.schedule_relative(
                window_ms / 1000,
                lambda *_: _flush(),
            )

        def _on_next(value: Any) -> None:
            nonlocal pending
            emit_now = False
            with lock:
                if mode is ReactivexStreamCoalesceMode.LEADING and timer is None:
                    emit_now = True
                    _schedule_flush()
                else:
                    pending = value
                    _schedule_flush()
            if emit_now:
                observer.on_next(value)

        def _on_error(err: Exception) -> None:
            nonlocal pending, timer
            with lock:
                if timer is not None:
                    timer.dispose()
                    timer = None
                pending = _NO_PENDING
            observer.on_error(err)

        def _on_completed() -> None:
            nonlocal timer
            with lock:
                if timer is not None:
                    timer.dispose()
                    timer = None
            _flush()
            observer.on_completed()

        subscription = source.subscribe(
            _on_next,
            _on_error,
            _on_completed,
            scheduler=scheduler,
        )

        def _dispose() -> None:
            nonlocal pending, timer
            subscription.dispose()
            with lock:
                pending = _NO_PENDING
                if timer is not None:
                    timer.dispose()
                    timer = None

        logger.debug(
            "Coalescing %s with window_ms=%d mode=%s",
            stream_name,
            window_ms,
            mode,
        )
        return Disposable(_dispose)

    return reactivex.create(_subscribe)


def _instrument_stream(
    source: reactivex.Observable[T],
    *,
    stream_name: str,
    log_interval_ms: int,
) -> reactivex.Observable[T]:
    if log_interval_ms <= 0:
        return source

    lock = RLock()
    subscriber_count = 0
    event_count = 0
    timer: Any | None = None

    def _log_stats() -> None:
        nonlocal event_count, timer
        with lock:
            timer = None
            if subscriber_count <= 0:
                event_count = 0
                return
            count = event_count
            event_count = 0
        logger.debug(
            "Stream stats for %s events=%d subscribers=%d interval_ms=%d",
            stream_name,
            count,
            subscriber_count,
            log_interval_ms,
        )
        _schedule_log()

    def _schedule_log() -> None:
        nonlocal timer
        with lock:
            if timer is not None:
                return
            timer = _STATS_SCHEDULER.schedule_relative(
                log_interval_ms / 1000,
                lambda *_: _log_stats(),
            )

    def _subscribe(observer: Any, scheduler: Any = None) -> Disposable:
        nonlocal subscriber_count
        with lock:
            subscriber_count += 1
            _schedule_log()

        def _on_next(value: Any) -> None:
            nonlocal event_count
            with lock:
                event_count += 1
            observer.on_next(value)

        def _on_error(err: Exception) -> None:
            observer.on_error(err)

        def _on_completed() -> None:
            observer.on_completed()

        subscription = source.subscribe(
            _on_next,
            _on_error,
            _on_completed,
            scheduler=scheduler,
        )

        def _dispose() -> None:
            nonlocal subscriber_count, timer
            subscription.dispose()
            with lock:
                subscriber_count -= 1
                if subscriber_count <= 0 and timer is not None:
                    timer.dispose()
                    timer = None

        return Disposable(_dispose)

    return reactivex.create(_subscribe)


def share_stream(
    source: reactivex.Observable[T],
    *,
    stream_name: str,
) -> reactivex.Observable[T]:
    """Share a stream using the configured strategy."""

    strategy = Configuration.reactivex_stream_share_strategy()
    coalesce_window_ms = Configuration.reactivex_stream_coalesce_window_ms()
    coalesce_mode = Configuration.reactivex_stream_coalesce_mode()
    stats_log_ms = Configuration.reactivex_stream_stats_log_ms()
    replay_window_ms = Configuration.reactivex_stream_replay_window_ms()
    auto_connect_min_subscribers = (
        Configuration.reactivex_stream_auto_connect_min_subscribers()
    )
    refcount_min_subscribers = (
        Configuration.reactivex_stream_refcount_min_subscribers()
    )
    refcount_grace_ms = Configuration.reactivex_stream_refcount_grace_ms()
    connect_mode = Configuration.reactivex_stream_connect_mode()
    replay_window_seconds = (
        None if replay_window_ms is None else replay_window_ms / 1000
    )
    source = _coalesce_stream(
        source,
        window_ms=coalesce_window_ms,
        mode=coalesce_mode,
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
        return _instrument_stream(
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
        return _instrument_stream(
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
        return _instrument_stream(
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
        return _instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=stats_log_ms,
        )
    if strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER:
        buffer_size = Configuration.reactivex_stream_replay_buffer()
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
        return _instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=stats_log_ms,
        )
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
        result = _replay(buffer_size).auto_connect(auto_connect_min_subscribers)
        return _instrument_stream(
            result,
            stream_name=stream_name,
            log_interval_ms=stats_log_ms,
        )
    raise ValueError(f"Unknown reactive stream share strategy: {strategy}")
