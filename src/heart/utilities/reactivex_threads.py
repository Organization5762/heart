from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from datetime import timedelta
from functools import cache
from threading import Lock, Thread
from typing import Any, Callable, TypeVar

import reactivex
from reactivex import Observable, Subject
from reactivex import operators as ops
from reactivex import pipe
from reactivex.abc import SchedulerBase
from reactivex.scheduler import (
    CurrentThreadScheduler,
    EventLoopScheduler,
    NewThreadScheduler,
    ThreadPoolScheduler,
    TimeoutScheduler,
)
from reactivex.typing import StartableTarget

from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_THREAD_LOCK = Lock()
_COALESCE_SCHEDULER = TimeoutScheduler()
shutdown: Subject[bool] = Subject()


@cache
def background_scheduler() -> ThreadPoolScheduler:
    return ThreadPoolScheduler(Configuration.reactivex_background_max_workers())


@cache
def input_scheduler() -> ThreadPoolScheduler:
    return ThreadPoolScheduler(Configuration.reactivex_input_max_workers())


def pipe_in_background(
    *items: Callable[[Observable], Observable] | Observable,
) -> Callable[[Observable], Observable] | Observable:
    if items and isinstance(items[0], Observable):
        source, *operations = items
        logger.debug("Building background pipeline.")
        return source.pipe(*operations)

    def operation(source: Observable) -> Observable:
        logger.debug("Building background pipeline.")
        return source.pipe(
            *items,
        )

    return operation


def pipe_in_main_thread(
    *items: Callable[[Observable], Observable] | Observable,
) -> Callable[[Observable], Observable] | Observable:
    if items and isinstance(items[0], Observable):
        source, *operations = items
        logger.debug("Building main-thread pipeline.")
        return source.pipe(ops.observe_on(CurrentThreadScheduler()), *operations)

    def operation(source: Observable) -> Observable:
        logger.debug("Building main-thread pipeline.")
        return source.pipe(
            ops.observe_on(CurrentThreadScheduler()),
            *items,
        )

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


def interval_in_background(period: timedelta) -> Observable[int]:
    return reactivex.interval(
        period,
        scheduler=background_scheduler(),
    ).pipe(ops.take_until(shutdown))


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
