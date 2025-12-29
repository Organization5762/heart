from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Callable

from reactivex.scheduler import ThreadPoolScheduler

from heart.utilities.env import Configuration

DEFAULT_MAX_WORKERS: int | None = None
BACKGROUND_THREAD_PREFIX = "heart-rx"
INPUT_THREAD_PREFIX = "heart-rx-input"


@dataclass
class _SchedulerState:
    lock: Lock
    scheduler: ThreadPoolScheduler | None = None


_BACKGROUND_SCHEDULER = _SchedulerState(lock=Lock())
_INPUT_SCHEDULER = _SchedulerState(lock=Lock())


def _build_scheduler(
    state: _SchedulerState,
    *,
    max_workers: int | None,
    default_workers: Callable[[], int],
    thread_name_prefix: str,
) -> ThreadPoolScheduler:
    if state.scheduler is None:
        with state.lock:
            if state.scheduler is None:
                resolved_workers = (
                    max_workers if max_workers is not None else default_workers()
                )
                print(f"Building scheduler with {resolved_workers} workers")
                state.scheduler = ThreadPoolScheduler(max_workers=resolved_workers)
    assert state.scheduler is not None
    return state.scheduler


def background_scheduler(
    max_workers: int | None = DEFAULT_MAX_WORKERS,
) -> ThreadPoolScheduler | None:
    return None
    """Return the shared scheduler for background reactivex work."""
    return _build_scheduler(
        _BACKGROUND_SCHEDULER,
        max_workers=max_workers,
        default_workers=Configuration.reactivex_background_max_workers,
        thread_name_prefix=BACKGROUND_THREAD_PREFIX,
    )


def input_scheduler(
    max_workers: int | None = DEFAULT_MAX_WORKERS,
) -> ThreadPoolScheduler | None:
    return None
    """Return the shared scheduler for key input reactivex work."""
    return _build_scheduler(
        _INPUT_SCHEDULER,
        max_workers=max_workers,
        default_workers=Configuration.reactivex_input_max_workers,
        thread_name_prefix=INPUT_THREAD_PREFIX,
    )
