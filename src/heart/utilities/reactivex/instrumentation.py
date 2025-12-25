from __future__ import annotations

from threading import RLock
from typing import Any, TypeVar

import reactivex
from reactivex.disposable import Disposable
from reactivex.scheduler import TimeoutScheduler

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
_STATS_SCHEDULER = TimeoutScheduler()


def instrument_stream(
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
