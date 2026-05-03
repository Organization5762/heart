from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from threading import Lock, Thread, get_ident
from typing import Any, TypeVar

import reactivex
from reactivex import Observable, Subject, create
from reactivex import operators as ops
from reactivex import pipe
from reactivex.abc import SchedulerBase
from reactivex.disposable import Disposable
from reactivex.scheduler import (EventLoopScheduler, NewThreadScheduler,
                                 ThreadPoolScheduler, TimeoutScheduler)
from reactivex.typing import StartableTarget

from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
FRAME_THREAD_LATENCY_STREAM = "frame_thread_handoff"
DEFAULT_DELIVERY_LATENCY_HISTORY_SIZE = 2048


@dataclass
class _SchedulerState:
    lock: Lock
    scheduler: SchedulerBase | None = None
    max_workers: int | None = None


@dataclass(frozen=True, slots=True)
class DeliveryLatencyStats:
    count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


@dataclass
class _FrameThreadTask:
    callback: Callable[[], None]
    enqueued_monotonic: float


class _LatencyRecorder:
    def __init__(self, history_size: int = DEFAULT_DELIVERY_LATENCY_HISTORY_SIZE) -> None:
        self._history_size = history_size
        self._history: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self._history_size)
        )
        self._lock = Lock()

    def record(self, stream_name: str, delay_s: float) -> None:
        with self._lock:
            self._history[stream_name].append(max(delay_s, 0.0))

    def snapshot(self) -> dict[str, DeliveryLatencyStats]:
        with self._lock:
            history = {
                stream_name: tuple(values)
                for stream_name, values in self._history.items()
                if values
            }
        return {
            stream_name: DeliveryLatencyStats(
                count=len(values),
                p50_ms=_percentile_ms(values, 0.50),
                p95_ms=_percentile_ms(values, 0.95),
                p99_ms=_percentile_ms(values, 0.99),
                max_ms=max(values) * 1000.0,
            )
            for stream_name, values in history.items()
        }

    def clear(self) -> None:
        with self._lock:
            self._history.clear()


_COALESCE_SCHEDULER = TimeoutScheduler()
_BACKGROUND_SCHEDULER = _SchedulerState(lock=Lock())
_BLOCKING_IO_SCHEDULER = _SchedulerState(lock=Lock())
_INPUT_SCHEDULER = _SchedulerState(lock=Lock())
_INTERVAL_SCHEDULER = _SchedulerState(lock=Lock())
_FRAME_THREAD_QUEUE: deque[_FrameThreadTask] = deque()
_FRAME_THREAD_QUEUE_LOCK = Lock()
_FRAME_THREAD_IDENT: int | None = None
_LATENCY_RECORDER = _LatencyRecorder()

shutdown: Subject[Any] = Subject()


def _percentile_ms(values: tuple[float, ...], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index] * 1000.0


def _build_scheduler(
    state: _SchedulerState,
    *,
    constructor: Callable[[], SchedulerBase],
    max_workers: int | None = None,
) -> SchedulerBase:
    if state.scheduler is None:
        with state.lock:
            if state.scheduler is None:
                state.scheduler = constructor()
                state.max_workers = max_workers
    assert state.scheduler is not None
    return state.scheduler


def _dispose_scheduler(scheduler: SchedulerBase | None) -> None:
    if scheduler is None:
        return
    dispose = getattr(scheduler, "dispose", None)
    if callable(dispose):
        dispose()


def create_default_thread_factory(name: str) -> Callable[[StartableTarget], Thread]:
    def default_thread_factory(target: StartableTarget) -> Thread:
        return Thread(target=target, daemon=False, name=name)

    return default_thread_factory


def _run_on_thread(target: StartableTarget, name: str) -> Thread:
    return Thread(target=target, daemon=False, name=name)


def background_scheduler() -> SchedulerBase:
    max_workers = Configuration.reactivex_background_max_workers()
    return _build_scheduler(
        _BACKGROUND_SCHEDULER,
        constructor=partial(ThreadPoolScheduler, max_workers=max_workers),
        max_workers=max_workers,
    )


def blocking_io_scheduler() -> SchedulerBase:
    max_workers = Configuration.reactivex_blocking_io_max_workers()
    return _build_scheduler(
        _BLOCKING_IO_SCHEDULER,
        constructor=partial(ThreadPoolScheduler, max_workers=max_workers),
        max_workers=max_workers,
    )


def input_scheduler() -> SchedulerBase:
    max_workers = Configuration.reactivex_input_max_workers()
    return _build_scheduler(
        _INPUT_SCHEDULER,
        constructor=partial(ThreadPoolScheduler, max_workers=max_workers),
        max_workers=max_workers,
    )


def interval_scheduler() -> SchedulerBase:
    return _build_scheduler(
        _INTERVAL_SCHEDULER,
        constructor=partial(
            EventLoopScheduler,
            thread_factory=create_default_thread_factory("reactivex-interval"),
        ),
    )


def coalesce_scheduler() -> SchedulerBase:
    return _COALESCE_SCHEDULER


def replay_scheduler() -> TimeoutScheduler:
    return TimeoutScheduler()


def interval_in_background(
    period: timedelta,
    *,
    name: str | None = None,
    scheduler: SchedulerBase | None = None,
) -> Observable[int]:
    resolved_scheduler = (
        scheduler
        or (
            EventLoopScheduler(
                thread_factory=partial(_run_on_thread, name=name),
            )
            if name is not None
            else interval_scheduler()
        )
    )
    return reactivex.interval(period=period, scheduler=resolved_scheduler).pipe(
        ops.take_until(shutdown),
    )


def delivery_latency_snapshot() -> dict[str, DeliveryLatencyStats]:
    return _LATENCY_RECORDER.snapshot()


def _enqueue_frame_thread_task(callback: Callable[[], None]) -> None:
    task = _FrameThreadTask(
        callback=callback,
        enqueued_monotonic=time.monotonic(),
    )
    with _FRAME_THREAD_QUEUE_LOCK:
        _FRAME_THREAD_QUEUE.append(task)


def drain_frame_thread_queue(max_items: int | None = None) -> int:
    global _FRAME_THREAD_IDENT
    _FRAME_THREAD_IDENT = get_ident()
    drained = 0
    while True:
        with _FRAME_THREAD_QUEUE_LOCK:
            if not _FRAME_THREAD_QUEUE:
                break
            task = _FRAME_THREAD_QUEUE.popleft()
        _LATENCY_RECORDER.record(
            FRAME_THREAD_LATENCY_STREAM,
            time.monotonic() - task.enqueued_monotonic,
        )
        task.callback()
        drained += 1
        if max_items is not None and drained >= max_items:
            break
    return drained


def on_frame_thread() -> bool:
    return _FRAME_THREAD_IDENT == get_ident()


def deliver_on_frame_thread(source: Observable[T]) -> Observable[T]:
    def _subscribe(observer: Any, scheduler: SchedulerBase | None = None) -> Disposable:
        disposed = False
        dispose_lock = Lock()

        def _deliver(callback: Callable[[], None]) -> None:
            def _run() -> None:
                nonlocal disposed
                with dispose_lock:
                    if disposed:
                        return
                callback()

            _enqueue_frame_thread_task(_run)

        subscription = source.subscribe(
            on_next=lambda value: _deliver(lambda: observer.on_next(value)),
            on_error=lambda error: _deliver(lambda: observer.on_error(error)),
            on_completed=lambda: _deliver(observer.on_completed),
            scheduler=scheduler,
        )

        def _dispose() -> None:
            nonlocal disposed
            with dispose_lock:
                disposed = True
            subscription.dispose()

        return Disposable(_dispose)

    return create(_subscribe)


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
    logger.debug("Building frame-thread pipeline.")
    return pipe(
        deliver_on_frame_thread(source),
        *[
            *operators,
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


def scheduler_diagnostics() -> dict[str, int | None]:
    return {
        "background_max_workers": _BACKGROUND_SCHEDULER.max_workers,
        "blocking_io_max_workers": _BLOCKING_IO_SCHEDULER.max_workers,
        "input_max_workers": _INPUT_SCHEDULER.max_workers,
    }


def reset_reactivex_threading_state_for_tests() -> None:
    global _FRAME_THREAD_IDENT
    for state in (
        _BACKGROUND_SCHEDULER,
        _BLOCKING_IO_SCHEDULER,
        _INPUT_SCHEDULER,
        _INTERVAL_SCHEDULER,
    ):
        with state.lock:
            scheduler = state.scheduler
            state.scheduler = None
            state.max_workers = None
        _dispose_scheduler(scheduler)
    with _FRAME_THREAD_QUEUE_LOCK:
        _FRAME_THREAD_QUEUE.clear()
    _FRAME_THREAD_IDENT = None
    _LATENCY_RECORDER.clear()


def share_sequence(sequence: Iterable[T]) -> Observable[T]:
    return reactivex.from_iterable(sequence).pipe(ops.share())
