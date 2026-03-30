from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from datetime import timedelta
from threading import Lock, Thread
from typing import Callable, TypeVar

import reactivex
from reactivex import Observable, Subject
from reactivex import operators as ops
from reactivex import pipe
from reactivex.scheduler import (EventLoopScheduler, NewThreadScheduler,
                                 TimeoutScheduler)
from reactivex.typing import StartableTarget

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_THREAD_LOCK = Lock()
_BACKGROUND_SCHEDULER = NewThreadScheduler(
    lambda target: _run_on_thread(target, "reactivex-background")
)
_COALESCE_SCHEDULER = TimeoutScheduler()
_INPUT_SCHEDULER = EventLoopScheduler(
    lambda target: _run_on_thread(target, "reactivex-input")
)
DEFAULT_INTERVAL_THREAD_NAME = "reactivex-interval"


def pipe_in_background(
    observable: Observable[T],
    *operations: Callable[[Observable], Observable],
) -> Observable[T]:
    """Apply ``operations`` after moving notifications onto a background thread."""

    logger.debug("Building background pipeline.")
    return observable.pipe(
        ops.observe_on(background_scheduler()),
        *operations,
    )


def pipe_in_main_thread(
    observable: Observable[T],
    *operations: Callable[[Observable], Observable],
) -> Observable[T]:
    """Apply ``operations`` without moving work off the caller's thread."""

    logger.debug("Building main-thread pipeline.")
    return observable.pipe(*operations)


@contextmanager
def background_threaded_observable(
    observable: Observable[T],
    name: str,
) -> Iterable[Observable[T]]:
    logger.debug("Starting background stream thread %s", name)
    subject = Subject()
    thread = Thread(
        name=name,
        target=_run_background_observable,
        args=(subject, observable),
        daemon=True,
    )
    thread.start()
    yield subject


def _run_background_observable(subject: Subject, observable: Observable) -> None:
    observable.subscribe(subject)


def share_sequence(sequence: Iterable[T]) -> Observable[T]:
    shared = Observable.from_iterable(sequence).pipe(
        ops.share(),
    )
    return shared


def coalesce_scheduler() -> TimeoutScheduler:
    return _COALESCE_SCHEDULER


def replay_scheduler() -> TimeoutScheduler:
    scheduler = TimeoutScheduler()
    return scheduler


def background_scheduler() -> NewThreadScheduler:
    return _BACKGROUND_SCHEDULER


def input_scheduler() -> EventLoopScheduler:
    return _INPUT_SCHEDULER


def interval_in_background(
    period: timedelta,
    *,
    name: str = DEFAULT_INTERVAL_THREAD_NAME,
) -> Observable[int]:
    """Return an interval observable whose notifications run on a background thread."""

    return reactivex.interval(period.total_seconds()).pipe(
        pipe_to_background_event_loop(name),
    )


def _run_on_thread(target: StartableTarget, name: str) -> Thread:
    with _THREAD_LOCK:
        thread = Thread(target=target, daemon=True, name=name)
        thread.start()
        return thread


def pipe_to_background_event_loop(
    name: str,
    *operations: Callable[[Observable], Observable],
) -> Callable[[Observable], Observable]:
    """Pipe a stream through an event loop running on a background thread."""

    scheduler = EventLoopScheduler(lambda target: _run_on_thread(target, name))
    return pipe(
        ops.observe_on(scheduler),
        *operations,
    )


def pipe_to_background_thread(
    name: str,
    *operations: Callable[[Observable], Observable],
) -> Callable[[Observable], Observable]:
    """Pipe a stream through a background thread executor."""

    scheduler = NewThreadScheduler(lambda target: _run_on_thread(target, name))
    return pipe(
        ops.observe_on(scheduler),
        *operations,
    )
