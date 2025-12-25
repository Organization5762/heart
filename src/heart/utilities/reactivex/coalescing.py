from __future__ import annotations

import time
from threading import RLock
from typing import Any, TypeVar

import reactivex
from reactivex.disposable import Disposable
from reactivex.scheduler import TimeoutScheduler

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
_COALESCE_SCHEDULER = TimeoutScheduler()
_NO_PENDING: Any = object()


def coalesce_latest(
    source: reactivex.Observable[T],
    *,
    window_ms: int,
    stream_name: str,
) -> reactivex.Observable[T]:
    if window_ms <= 0:
        return source

    def _subscribe(observer: Any, scheduler: Any = None) -> Disposable:
        lock = RLock()
        pending: Any = _NO_PENDING
        timer: Any | None = None
        due_time: float | None = None
        window_seconds = window_ms / 1000

        def _flush() -> None:
            nonlocal pending, timer, due_time
            with lock:
                value = pending
                pending = _NO_PENDING
                timer = None
                due_time = None
            if value is _NO_PENDING:
                return
            observer.on_next(value)

        def _schedule_flush(now: float) -> None:
            nonlocal timer, due_time
            if timer is not None:
                return
            due_time = now + window_seconds
            timer = _COALESCE_SCHEDULER.schedule_relative(
                window_seconds,
                lambda *_: _flush(),
            )

        def _on_next(value: Any) -> None:
            nonlocal pending, timer, due_time
            now = time.monotonic()
            flush_value: Any = _NO_PENDING
            with lock:
                if pending is not _NO_PENDING and due_time is not None and now >= due_time:
                    flush_value = pending
                    pending = _NO_PENDING
                    if timer is not None:
                        timer.dispose()
                        timer = None
                    due_time = None
                pending = value
                _schedule_flush(now)
            if flush_value is not _NO_PENDING:
                observer.on_next(flush_value)

        def _on_error(err: Exception) -> None:
            nonlocal pending, timer, due_time
            with lock:
                if timer is not None:
                    timer.dispose()
                    timer = None
                pending = _NO_PENDING
                due_time = None
            observer.on_error(err)

        def _on_completed() -> None:
            nonlocal timer, due_time
            with lock:
                if timer is not None:
                    timer.dispose()
                    timer = None
                due_time = None
            _flush()
            observer.on_completed()

        subscription = source.subscribe(
            _on_next,
            _on_error,
            _on_completed,
            scheduler=scheduler,
        )

        def _dispose() -> None:
            nonlocal pending, timer, due_time
            subscription.dispose()
            with lock:
                pending = _NO_PENDING
                if timer is not None:
                    timer.dispose()
                    timer = None
                due_time = None

        logger.debug(
            "Coalescing %s with window_ms=%d",
            stream_name,
            window_ms,
        )
        return Disposable(_dispose)

    return reactivex.create(_subscribe)
