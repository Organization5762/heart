from datetime import timedelta

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

logger = get_logger(__name__)


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


def _share_stream(
    source: reactivex.Observable,
    connect_mode: ReactivexStreamConnectMode,
    share_strategy: ReactivexStreamShareStrategy,
    replay_buffer_size: int,
    replay_window: timedelta | None,
    subscriber_limit: int,
    scheduler: TimeoutScheduler,
) -> reactivex.Observable:
    replay_enabled = _should_replay(
        share_strategy,
        replay_buffer_size,
        replay_window,
    )
    if replay_enabled:
        return source.pipe(
            ops.replay(
                buffer_size=replay_buffer_size,
                window=replay_window,
                scheduler=scheduler,
            ),
            ops.ref_count(),
        )
    return source.pipe(ops.share())


class _CoalesceBuffer:
    def __init__(self, buffer_time_ms: int):
        self._buffer_time_ms = buffer_time_ms

    def __call__(self, source: reactivex.Observable) -> reactivex.Observable:
        return source.pipe(
            ops.buffer_with_time(
                timedelta(milliseconds=self._buffer_time_ms),
                scheduler=TimeoutScheduler(),
            ),
            ops.filter(lambda buffer: len(buffer) > 0),
        )


class _ShareStream:
    def __init__(
        self,
        connect_mode: ReactivexStreamConnectMode,
        share_strategy: ReactivexStreamShareStrategy,
        replay_buffer_size: int,
        replay_window: timedelta | None,
        subscriber_limit: int,
        coalesce_window_ms: int,
    ):
        self._connect_mode = connect_mode
        self._share_strategy = share_strategy
        self._replay_buffer_size = replay_buffer_size
        self._replay_window = replay_window
        self._subscriber_limit = subscriber_limit
        self._coalesce_window_ms = coalesce_window_ms

    def __call__(self, source: reactivex.Observable) -> reactivex.Observable:
        scheduler = TimeoutScheduler()
        if self._connect_mode == ReactivexStreamConnectMode.eager:
            source = source.pipe(ops.publish(), ops.connect())
        shared = _share_stream(
            source,
            self._connect_mode,
            self._share_strategy,
            self._replay_buffer_size,
            self._replay_window,
            self._subscriber_limit,
            scheduler,
        )
        if self._coalesce_window_ms > 0:
            return shared.pipe(
                _CoalesceBuffer(self._coalesce_window_ms),
                ops.map(lambda buffer: buffer[-1]),
            )
        return shared


class _RefcountGrace:
    def __init__(self, grace_period_ms: int, min_subscribers: int):
        self._grace_period_ms = grace_period_ms
        self._min_subscribers = min_subscribers

    def __call__(self, source: reactivex.Observable) -> reactivex.Observable:
        def subscribe(observer, scheduler=None) -> Disposable:
            return source.subscribe(observer, scheduler=scheduler)

        return reactivex.defer(subscribe)


def share_stream(
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
    """Return a shared observable with support for configurable replay strategies.

    The share strategy and connection mode are driven by environment configuration, so
    this helper keeps the behaviour consistent across modules.
    """

    shared = _ShareStream(
        connect_mode,
        share_strategy,
        replay_buffer_size,
        replay_window,
        subscriber_limit,
        coalesce_window_ms,
    )(source)
    if grace_period_ms > 0 or min_subscribers > 1:
        shared = shared.pipe(_RefcountGrace(grace_period_ms, min_subscribers))
    return instrument_stream(shared)


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
        connect_mode,
        share_strategy,
        replay_buffer_size,
        replay_window,
        subscriber_limit,
        coalesce_window_ms,
        grace_period_ms,
        min_subscribers,
    )
    if share_strategy is ReactivexStreamShareStrategy.coalesce_latest:
        return shared.pipe(coalesce_latest(coalesce_window_ms))
    return shared
