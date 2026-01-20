from datetime import timedelta
from threading import RLock
from typing import Any, TypeVar, cast

import reactivex
from reactivex import operators as ops
from reactivex.disposable import Disposable
from reactivex.scheduler import TimeoutScheduler

from heart.utilities.env import (
    ReactivexStreamConnectMode,
    ReactivexStreamShareStrategy,
)
from heart.utilities.logging import get_logger
from heart.utilities.reactivex.coalescing import coalesce_latest
from heart.utilities.reactivex.instrumentation import instrument_stream
from heart.utilities.reactivex.settings import StreamShareSettings
from heart.utilities.reactivex.types import ConnectableStream

logger = get_logger(__name__)

T = TypeVar("T")
_REPLAY_SCHEDULER = TimeoutScheduler()
_GRACE_SCHEDULER = TimeoutScheduler()

def _get_replay_window(max_age_ms: int | None) -> timedelta | None:
    if max_age_ms is None:
        return None
    return timedelta(milliseconds=max_age_ms)


def _should_replay(
    share_strategy: ReactivexStreamShareStrategy,
    replay_buffer_size: int,
    replay_window: timedelta | None,
) -> bool:
    if share_strategy is ReactivexStreamShareStrategy.replay_latest:
        return True
    if share_strategy is ReactivexStreamShareStrategy.replay_buffer:
        return replay_buffer_size > 0
    if share_strategy is ReactivexStreamShareStrategy.replay_window:
        return replay_window is not None
    return False


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


def _replay(
    source: reactivex.Observable[T],
    *,
    buffer_size: int,
    replay_window: timedelta | None,
) -> ConnectableStream[T]:
    if replay_window is None:
        return cast(
            ConnectableStream[T],
            source.pipe(ops.replay(buffer_size=buffer_size)),
        )
    return cast(
        ConnectableStream[T],
        source.pipe(
            ops.replay(
                buffer_size=buffer_size,
                window=replay_window.total_seconds(),
                scheduler=_REPLAY_SCHEDULER,
            )
        ),
    )


def _coalesce_if_needed(
    source: reactivex.Observable[T],
    *,
    coalesce_window_ms: int,
    stream_name: str,
) -> reactivex.Observable[T]:
    if coalesce_window_ms <= 0:
        return source
    return source.pipe(
        coalesce_latest(coalesce_window_ms, stream_name=stream_name),
    )


def share_stream(
    source: reactivex.Observable[T],
    connect_mode: ReactivexStreamConnectMode | None = None,
    share_strategy: ReactivexStreamShareStrategy | None = None,
    replay_buffer_size: int | None = None,
    replay_window: timedelta | None = None,
    subscriber_limit: int = 0,
    coalesce_window_ms: int | None = None,
    grace_period_ms: int | None = None,
    min_subscribers: int | None = None,
    *,
    stream_name: str | None = None,
) -> reactivex.Observable[T]:
    """Return a shared observable with support for configurable replay strategies.

    The share strategy and connection mode are driven by environment configuration, so
    this helper keeps the behaviour consistent across modules.
    """

    settings = StreamShareSettings.from_environment()
    resolved_connect_mode = connect_mode or settings.connect_mode
    resolved_share_strategy = share_strategy or settings.strategy
    resolved_replay_buffer = (
        replay_buffer_size
        if replay_buffer_size is not None
        else settings.replay_buffer()
    )
    resolved_replay_window = (
        replay_window
        if replay_window is not None
        else _get_replay_window(settings.replay_window_ms)
    )
    resolved_coalesce_window = (
        coalesce_window_ms
        if coalesce_window_ms is not None
        else settings.coalesce_window_ms
    )
    resolved_min_subscribers = (
        min_subscribers
        if min_subscribers is not None
        else settings.refcount_min_subscribers
    )
    resolved_grace_period = (
        grace_period_ms
        if grace_period_ms is not None
        else settings.refcount_grace_ms
    )

    resolved_connect_mode = ReactivexStreamConnectMode(resolved_connect_mode)
    resolved_share_strategy = ReactivexStreamShareStrategy(resolved_share_strategy)

    settings = StreamShareSettings(
        strategy=resolved_share_strategy,
        coalesce_window_ms=resolved_coalesce_window,
        stats_log_ms=settings.stats_log_ms,
        replay_window_ms=(
            int(resolved_replay_window.total_seconds() * 1000)
            if resolved_replay_window is not None
            else None
        ),
        auto_connect_min_subscribers=settings.auto_connect_min_subscribers,
        refcount_min_subscribers=resolved_min_subscribers,
        refcount_grace_ms=resolved_grace_period,
        connect_mode=resolved_connect_mode,
    )

    stream_label = stream_name or "reactivex-stream"
    replay_window_setting = resolved_replay_window

    if resolved_share_strategy is ReactivexStreamShareStrategy.SHARE:
        if resolved_grace_period > 0 or resolved_min_subscribers > 1:
            shared = _share_with_refcount_grace(
                cast(ConnectableStream[T], source.pipe(ops.publish())),
                grace_ms=resolved_grace_period,
                min_subscribers=resolved_min_subscribers,
                connect_mode=resolved_connect_mode,
                stream_name=stream_label,
            )
        else:
            shared = source.pipe(ops.share())
        shared = _coalesce_if_needed(
            shared,
            coalesce_window_ms=resolved_coalesce_window,
            stream_name=stream_label,
        )
        return instrument_stream(
            shared,
            stream_name=stream_label,
            log_interval_ms=settings.stats_log_ms,
        )

    if resolved_share_strategy is ReactivexStreamShareStrategy.SHARE_AUTO_CONNECT:
        shared = source.pipe(ops.publish()).auto_connect(
            settings.auto_connect_min_subscribers
        )
        shared = _coalesce_if_needed(
            shared,
            coalesce_window_ms=resolved_coalesce_window,
            stream_name=stream_label,
        )
        return instrument_stream(
            shared,
            stream_name=stream_label,
            log_interval_ms=settings.stats_log_ms,
        )

    if resolved_share_strategy is ReactivexStreamShareStrategy.REPLAY_LATEST:
        replayed = _replay(
            source,
            buffer_size=1,
            replay_window=replay_window_setting,
        )
        if resolved_grace_period > 0 or resolved_min_subscribers > 1:
            shared = _share_with_refcount_grace(
                replayed,
                grace_ms=resolved_grace_period,
                min_subscribers=resolved_min_subscribers,
                connect_mode=resolved_connect_mode,
                stream_name=stream_label,
            )
        else:
            shared = replayed.pipe(ops.ref_count())
        shared = _coalesce_if_needed(
            shared,
            coalesce_window_ms=resolved_coalesce_window,
            stream_name=stream_label,
        )
        return instrument_stream(
            shared,
            stream_name=stream_label,
            log_interval_ms=settings.stats_log_ms,
        )

    if resolved_share_strategy is ReactivexStreamShareStrategy.REPLAY_LATEST_AUTO_CONNECT:
        shared = _replay(
            source,
            buffer_size=1,
            replay_window=replay_window_setting,
        ).auto_connect(settings.auto_connect_min_subscribers)
        shared = _coalesce_if_needed(
            shared,
            coalesce_window_ms=resolved_coalesce_window,
            stream_name=stream_label,
        )
        return instrument_stream(
            shared,
            stream_name=stream_label,
            log_interval_ms=settings.stats_log_ms,
        )

    if resolved_share_strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER:
        replayed = _replay(
            source,
            buffer_size=resolved_replay_buffer,
            replay_window=replay_window_setting,
        )
        if resolved_grace_period > 0 or resolved_min_subscribers > 1:
            shared = _share_with_refcount_grace(
                replayed,
                grace_ms=resolved_grace_period,
                min_subscribers=resolved_min_subscribers,
                connect_mode=resolved_connect_mode,
                stream_name=stream_label,
            )
        else:
            shared = replayed.pipe(ops.ref_count())
        shared = _coalesce_if_needed(
            shared,
            coalesce_window_ms=resolved_coalesce_window,
            stream_name=stream_label,
        )
        return instrument_stream(
            shared,
            stream_name=stream_label,
            log_interval_ms=settings.stats_log_ms,
        )

    if resolved_share_strategy is ReactivexStreamShareStrategy.REPLAY_BUFFER_AUTO_CONNECT:
        shared = _replay(
            source,
            buffer_size=resolved_replay_buffer,
            replay_window=replay_window_setting,
        ).auto_connect(settings.auto_connect_min_subscribers)
        shared = _coalesce_if_needed(
            shared,
            coalesce_window_ms=resolved_coalesce_window,
            stream_name=stream_label,
        )
        return instrument_stream(
            shared,
            stream_name=stream_label,
            log_interval_ms=settings.stats_log_ms,
        )

    raise ValueError(
        f"Unknown reactive stream share strategy: {resolved_share_strategy}"
    )


def share_stream_from_env(
    source: reactivex.Observable,
    connect_mode: ReactivexStreamConnectMode,
    share_strategy: ReactivexStreamShareStrategy,
    replay_buffer_size: int,
    replay_window: timedelta | None,
    subscriber_limit: int,
    coalesce_window_ms: int,
    grace_period_ms: int,
    min_subscribers: int,
) -> reactivex.Observable:
    """Return a shared observable configured from environment variables."""

    logger.debug(
        "Creating shared stream with mode=%s strategy=%s buffer_size=%d window=%s subscriber_limit=%d coalesce_ms=%d grace_ms=%d min_subscribers=%d",
        connect_mode,
        share_strategy,
        replay_buffer_size,
        replay_window,
        subscriber_limit,
        coalesce_window_ms,
        grace_period_ms,
        min_subscribers,
    )
    shared = share_stream(
        source,
        connect_mode=connect_mode,
        share_strategy=share_strategy,
        replay_buffer_size=replay_buffer_size,
        replay_window=replay_window,
        subscriber_limit=subscriber_limit,
        coalesce_window_ms=coalesce_window_ms,
        grace_period_ms=grace_period_ms,
        min_subscribers=min_subscribers,
    )
    return shared
