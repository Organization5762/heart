from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from threading import Lock, Thread
from typing import Any, TypeVar

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


@dataclass
class _SchedulerState:
    lock: Lock
    scheduler: SchedulerBase | None = None


_COALESCE_SCHEDULER = TimeoutScheduler()
_INPUT_SCHEDULER = _SchedulerState(lock=Lock())
_INTERVAL_SCHEDULER = _SchedulerState(lock=Lock())
_MAIN_THREAD_SCHEDULER = TimeoutScheduler()

shutdown: Subject[Any] = Subject()


def _build_scheduler(
    state: _SchedulerState,
    *,
    constructor: Callable[[], SchedulerBase],
) -> SchedulerBase:
    if state.scheduler is None:
        with state.lock:
            if state.scheduler is None:
                state.scheduler = constructor()
    assert state.scheduler is not None
    return state.scheduler


def create_default_thread_factory(name: str) -> Callable[[StartableTarget], Thread]:
    def default_thread_factory(target: StartableTarget) -> Thread:
        return Thread(target=target, daemon=False, name=name)

    return default_thread_factory


def _run_on_thread(target: StartableTarget, name: str) -> Thread:
    return Thread(target=target, daemon=False, name=name)


def background_scheduler() -> SchedulerBase:
    return NewThreadScheduler(
        thread_factory=create_default_thread_factory("reactivex-background")
    )


def input_scheduler() -> SchedulerBase:
    return _build_scheduler(
        _INPUT_SCHEDULER,
        constructor=partial(
            EventLoopScheduler,
            thread_factory=create_default_thread_factory("reactivex-input"),
        ),
    )


def interval_scheduler() -> SchedulerBase:
    return _build_scheduler(
        _INTERVAL_SCHEDULER,
        constructor=partial(
            EventLoopScheduler,
            thread_factory=create_default_thread_factory("reactivex-interval"),
        ),
    )


def main_thread_scheduler() -> SchedulerBase:
    return _MAIN_THREAD_SCHEDULER


def coalesce_scheduler() -> SchedulerBase:
    return _COALESCE_SCHEDULER


def replay_scheduler() -> TimeoutScheduler:
    return TimeoutScheduler()


def interval_in_background(
    period: timedelta,
    *,
    name: str | None = None,
) -> Observable[int]:
    scheduler = (
        EventLoopScheduler(
            thread_factory=partial(_run_on_thread, name=name),
        )
        if name is not None
        else interval_scheduler()
    )
    return reactivex.interval(period=period, scheduler=scheduler).pipe(
        ops.take_until(shutdown),
    )


def pipe_in_background(source: Observable[T], *operators: Any) -> Observable[Any]:
    logger.debug("Building background pipeline.")
    return pipe(
        source,
        *[
            *operators,
            ops.share(),
        ],
    )


def pipe_in_main_thread(source: Observable[T], *operators: Any) -> Observable[Any]:
    logger.debug("Building main-thread pipeline.")
    return pipe(
        source,
        *[
            ops.subscribe_on(main_thread_scheduler()),
            *operators,
            ops.observe_on(main_thread_scheduler()),
            ops.share(),
        ],
    )


def pipe_to_background_event_loop(
    source: Observable[T],
    name: str,
    *operators: Any,
) -> Observable[Any]:
    """Pipe a stream through an event loop running on a background thread."""

    scheduler = EventLoopScheduler(
        thread_factory=partial(_run_on_thread, name=name),
    )
    return pipe(
        source,
        ops.observe_on(scheduler),
        *operators,
    )


def pipe_to_background_thread(
    source: Observable[T],
    name: str,
    *operators: Any,
) -> Observable[Any]:
    """Pipe a stream through a background thread executor."""

    scheduler = NewThreadScheduler(
        thread_factory=partial(_run_on_thread, name=name),
    )
    return pipe(
        source,
        ops.observe_on(scheduler),
        *operators,
    )


@contextmanager
def background_threaded_observable(
    observable: Observable[T],
    name: str,
) -> Iterator[Observable[T]]:
    logger.debug("Starting background stream thread %s", name)
    subject: Subject[T] = Subject()
    thread = Thread(
        name=name,
        target=_run_background_observable,
        args=(subject, observable),
        daemon=True,
    )
    thread.start()
    yield subject


def _run_background_observable(
    subject: Subject[T],
    observable: Observable[T],
) -> None:
    observable.subscribe(subject)


def share_sequence(sequence: Iterable[T]) -> Observable[T]:
    return reactivex.from_iterable(sequence).pipe(ops.share())
