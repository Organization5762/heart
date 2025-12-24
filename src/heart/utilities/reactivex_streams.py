from __future__ import annotations

from threading import RLock
from typing import Any, Protocol, TypeVar, cast

import reactivex
from reactivex import operators as ops
from reactivex.disposable import Disposable
from reactivex.scheduler import TimeoutScheduler

from heart.utilities.env import (Configuration, ReactivexStreamConnectMode,
                                 ReactivexStreamShareStrategy)
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
_REPLAY_SCHEDULER = TimeoutScheduler()
_GRACE_SCHEDULER = TimeoutScheduler()


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
            if connection is None or subscriber_count > 0:
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
            ):
                logger.debug(
                    "Connecting %s with refcount grace (grace_ms=%d, mode=%s)",
                    stream_name,
                    grace_ms,
                    connect_mode,
                )
                connection = connectable.connect()

        subscription = connectable.subscribe(observer, scheduler=scheduler)
        if connect_mode is ReactivexStreamConnectMode.LAZY:
            with lock:
                if connection is None and subscriber_count > 0:
                    logger.debug(
                        "Connecting %s with refcount grace (grace_ms=%d, mode=%s)",
                        stream_name,
                        grace_ms,
                        connect_mode,
                    )
                    connection = connectable.connect()

        def _dispose() -> None:
            nonlocal subscriber_count, disconnect_timer
            subscription.dispose()
            with lock:
                subscriber_count -= 1
                if subscriber_count > 0 or connection is None:
                    return
                if grace_ms <= 0:
                    _disconnect()
                    return
                logger.debug(
                    "Scheduling disconnect for %s in %dms", stream_name, grace_ms
                )
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

    strategy = Configuration.reactivex_stream_share_strategy()
    replay_window_ms = Configuration.reactivex_stream_replay_window_ms()
    auto_connect_min_subscribers = (
        Configuration.reactivex_stream_auto_connect_min_subscribers()
    )
    refcount_grace_ms = Configuration.reactivex_stream_refcount_grace_ms()
    connect_mode = Configuration.reactivex_stream_connect_mode()
    replay_window_seconds = (
        None if replay_window_ms is None else replay_window_ms / 1000
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
            "Sharing %s with share (refcount_grace_ms=%d)",
            stream_name,
            refcount_grace_ms,
        )
        if refcount_grace_ms > 0:
            return _share_with_refcount_grace(
                cast(ConnectableStream[T], source.pipe(ops.publish())),
                grace_ms=refcount_grace_ms,
                connect_mode=connect_mode,
                stream_name=stream_name,
            )
        return source.pipe(ops.share())
    if strategy is ReactivexStreamShareStrategy.SHARE_AUTO_CONNECT:
        logger.debug(
            "Sharing %s with share_auto_connect (min_subscribers=%d)",
            stream_name,
            auto_connect_min_subscribers,
        )
        return source.pipe(ops.publish()).auto_connect(auto_connect_min_subscribers)
    if strategy is ReactivexStreamShareStrategy.REPLAY_LATEST:
        logger.debug(
            "Sharing %s with replay_latest (window_ms=%s, refcount_grace_ms=%d)",
            stream_name,
            replay_window_ms,
            refcount_grace_ms,
        )
        replayed = _replay(1)
        if refcount_grace_ms > 0:
            return _share_with_refcount_grace(
                replayed,
                grace_ms=refcount_grace_ms,
                connect_mode=connect_mode,
                stream_name=stream_name,
            )
        return replayed.pipe(ops.ref_count())
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
            "Sharing %s with replay_buffer=%d (window_ms=%s, refcount_grace_ms=%d)",
            stream_name,
            buffer_size,
            replay_window_ms,
            refcount_grace_ms,
        )
        replayed = _replay(buffer_size)
        if refcount_grace_ms > 0:
            return _share_with_refcount_grace(
                replayed,
                grace_ms=refcount_grace_ms,
                connect_mode=connect_mode,
                stream_name=stream_name,
            )
        return replayed.pipe(ops.ref_count())
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
