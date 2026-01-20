import time
from threading import RLock, Timer
from typing import Any, Callable, TypeVar

import reactivex
from reactivex.disposable import Disposable

from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import _COALESCE_SCHEDULER

logger = get_logger(__name__)

T = TypeVar("T")
CoalesceCallable = Callable[[reactivex.Observable[T]], reactivex.Observable[T]]
_NO_PENDING: Any = object()


def coalesce_latest(
    window_ms: int,
    *,
    stream_name: str | None = None,
) -> CoalesceCallable:
    """Coalesce emissions within the buffer window into the last value."""

    if window_ms <= 0:
        return lambda source: source

    def coalesce(source: reactivex.Observable[T]) -> reactivex.Observable[T]:
        def _subscribe(observer: Any, scheduler: Any = None) -> Disposable:
            del scheduler
            lock = RLock()
            pending: Any = _NO_PENDING
            timer: Any | None = None
            fallback_timer: Timer | None = None
            due_time: float | None = None
            window_seconds = window_ms / 1000

            def _cancel_timers() -> None:
                nonlocal timer, fallback_timer
                if timer is not None:
                    timer.dispose()
                    timer = None
                if fallback_timer is not None:
                    fallback_timer.cancel()
                    fallback_timer = None

            def _flush() -> None:
                nonlocal pending, due_time
                with lock:
                    value = pending
                    pending = _NO_PENDING
                    _cancel_timers()
                    due_time = None
                if value is _NO_PENDING:
                    return
                observer.on_next(value)

            def _schedule_flush(now: float) -> None:
                nonlocal timer, fallback_timer, due_time
                if timer is not None or fallback_timer is not None:
                    if due_time is not None and now >= due_time:
                        _cancel_timers()
                        due_time = None
                    else:
                        return
                due_time = now + window_seconds
                timer = _COALESCE_SCHEDULER.schedule_relative(
                    window_seconds,
                    lambda *_: _flush(),
                )
                fallback_timer = Timer(window_seconds, _flush)
                fallback_timer.daemon = True
                fallback_timer.start()

            def _on_next(value: Any) -> None:
                nonlocal pending, due_time
                now = time.monotonic()
                flush_value: Any = _NO_PENDING
                with lock:
                    if (
                        pending is not _NO_PENDING
                        and due_time is not None
                        and now >= due_time
                    ):
                        flush_value = pending
                        pending = _NO_PENDING
                        _cancel_timers()
                        due_time = None
                    pending = value
                    _schedule_flush(now)
                if flush_value is not _NO_PENDING:
                    observer.on_next(flush_value)

            def _on_error(err: Exception) -> None:
                nonlocal pending, due_time
                with lock:
                    _cancel_timers()
                    pending = _NO_PENDING
                    due_time = None
                observer.on_error(err)

            def _on_completed() -> None:
                nonlocal due_time
                with lock:
                    _cancel_timers()
                    due_time = None
                _flush()
                observer.on_completed()

            subscription = source.subscribe(
                _on_next,
                _on_error,
                _on_completed,
                scheduler=_COALESCE_SCHEDULER,
            )

            def _dispose() -> None:
                nonlocal pending, due_time
                subscription.dispose()
                with lock:
                    pending = _NO_PENDING
                    _cancel_timers()
                    due_time = None

            logger.debug(
                "Coalescing %s with window_ms=%d",
                stream_name or "reactivex-stream",
                window_ms,
            )
            return Disposable(_dispose)

        return reactivex.create(_subscribe)

    return coalesce
