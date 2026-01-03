from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from threading import Lock, Thread
from typing import Any, Callable, TypeVar

import reactivex
from reactivex import Observable, Subject
from reactivex import operators as ops
from reactivex import pipe
from reactivex.abc import SchedulerBase
from reactivex.scheduler import (EventLoopScheduler, NewThreadScheduler,
                                 TimeoutScheduler)
from reactivex.typing import StartableTarget

T = TypeVar("T")
DEFAULT_MAX_WORKERS: int | None = None


@dataclass
class _SchedulerState:
    lock: Lock
    scheduler: SchedulerBase | None = None

    def get_scheduler(self) -> SchedulerBase:
        assert self.scheduler is not None
        return self.scheduler


_BACKGROUND_SCHEDULER = _SchedulerState(lock=Lock())
_INPUT_SCHEDULER = _SchedulerState(lock=Lock())
_INTERVAL_SCHEDULER = _SchedulerState(lock=Lock())
_COALESCE_SCHEDULER =_SchedulerState(lock=Lock(), scheduler=TimeoutScheduler())
_MAIN_THREAD_SCHEDULER =_SchedulerState(lock=Lock(), scheduler=TimeoutScheduler())

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
        result = Thread(
            target=target, daemon=False, name=name
        )
        return result
    return default_thread_factory


def background_scheduler() -> SchedulerBase:
    return NewThreadScheduler(thread_factory=create_default_thread_factory("reactivex-background"))


def input_scheduler() -> SchedulerBase:
    return _build_scheduler(
        _INPUT_SCHEDULER,
        constructor=partial(EventLoopScheduler, thread_factory=create_default_thread_factory("reactivex-input"))
    )

def interval_scheduler() -> SchedulerBase:
    return _build_scheduler(
        _INTERVAL_SCHEDULER,
        constructor=partial(EventLoopScheduler, thread_factory=create_default_thread_factory("reactivex-interval"))
    )

def main_thread_scheduler() -> SchedulerBase:
    return _MAIN_THREAD_SCHEDULER.get_scheduler()

def coalesce_scheduler() -> SchedulerBase:
    return _COALESCE_SCHEDULER.get_scheduler()

def interval_in_background(period: timedelta) -> Observable[Any]:
    return reactivex.interval(period=period, scheduler=interval_scheduler()).pipe(
        ops.take_until(shutdown),
    )

def pipe_in_background(source: Observable[T], *operators: Any) -> Observable[Any]:
    return pipe(
        source,
        *[
            ops.subscribe_on(background_scheduler()),
            *operators,
            ops.observe_on(main_thread_scheduler()),
            ops.share(),
        ]
    )

def pipe_in_main_thread(source: Observable[T], *operators: Any) -> Observable[Any]:
    return pipe(
        source,
        *[
            ops.subscribe_on(main_thread_scheduler()),
            *operators,
            ops.observe_on(main_thread_scheduler()),
            ops.share(),
        ]
    )
