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
from reactivex.abc import SchedulerBase
from reactivex.scheduler import (EventLoopScheduler, NewThreadScheduler,
                                 TimeoutScheduler)
from reactivex.typing import StartableTarget

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_THREAD_LOCK = Lock()
_COALESCE_SCHEDULER = TimeoutScheduler()
_BACKGROUND_SCHEDULER: SchedulerBase | None = None
_INPUT_SCHEDULER: SchedulerBase | None = None

BACKGROUND_THREAD_NAME = "reactivex-background"
INPUT_THREAD_NAME = "reactivex-input"
shutdown: Subject[bool] = Subject()


def pipe_in_background(
    source: Observable | Callable[[Observable], Observable],
    *operations: Callable[[Observable], Observable],
) -> Observable | Callable[[Observable], Observable]:
    if isinstance(source, Observable):
        logger.debug("Building background pipeline.")
        return source.pipe(*operations)

    operation_chain = (source, *operations)

    def operation(stream: Observable) -> Observable:
        logger.debug("Building background pipeline.")
        return stream.pipe(*operation_chain)

    return operation


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


def _run_on_thread(target: StartableTarget, name: str) -> Thread:
    with _THREAD_LOCK:
        thread = Thread(target=target, daemon=True, name=name)
        thread.start()
        return thread


def background_scheduler() -> SchedulerBase:
    global _BACKGROUND_SCHEDULER
    if _BACKGROUND_SCHEDULER is None:
        _BACKGROUND_SCHEDULER = EventLoopScheduler(
            lambda target: _run_on_thread(target, BACKGROUND_THREAD_NAME)
        )
    return _BACKGROUND_SCHEDULER


def input_scheduler() -> SchedulerBase:
    global _INPUT_SCHEDULER
    if _INPUT_SCHEDULER is None:
        _INPUT_SCHEDULER = EventLoopScheduler(
            lambda target: _run_on_thread(target, INPUT_THREAD_NAME)
        )
    return _INPUT_SCHEDULER


def interval_in_background(period: timedelta) -> Observable[int]:
    return reactivex.interval(
        period.total_seconds(),
        scheduler=background_scheduler(),
    )


def pipe_in_main_thread(
    source: Observable[T],
    *operations: Callable[[Observable], Observable],
) -> Observable:
    return source.pipe(*operations)


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
