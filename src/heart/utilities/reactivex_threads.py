from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from reactivex.scheduler import ThreadPoolScheduler

from heart.utilities.env import Configuration

_SCHEDULER_LOCK = Lock()
_SCHEDULER: ThreadPoolScheduler | None = None
_EXECUTOR: ThreadPoolExecutor | None = None
_INPUT_SCHEDULER_LOCK = Lock()
_INPUT_SCHEDULER: ThreadPoolScheduler | None = None
_INPUT_EXECUTOR: ThreadPoolExecutor | None = None


def background_scheduler(max_workers: int | None = None) -> ThreadPoolScheduler:
    """Return the shared scheduler for background reactivex work."""
    global _SCHEDULER, _EXECUTOR
    if _SCHEDULER is None:
        with _SCHEDULER_LOCK:
            if _SCHEDULER is None:
                resolved_workers = (
                    max_workers
                    if max_workers is not None
                    else Configuration.reactivex_background_max_workers()
                )
                _EXECUTOR = ThreadPoolExecutor(
                    max_workers=resolved_workers,
                    thread_name_prefix="heart-rx",
                )
                _SCHEDULER = ThreadPoolScheduler(_EXECUTOR)
    return _SCHEDULER


def input_scheduler(max_workers: int | None = None) -> ThreadPoolScheduler:
    """Return the shared scheduler for key input reactivex work."""
    global _INPUT_SCHEDULER, _INPUT_EXECUTOR
    if _INPUT_SCHEDULER is None:
        with _INPUT_SCHEDULER_LOCK:
            if _INPUT_SCHEDULER is None:
                resolved_workers = (
                    max_workers
                    if max_workers is not None
                    else Configuration.reactivex_input_max_workers()
                )
                _INPUT_EXECUTOR = ThreadPoolExecutor(
                    max_workers=resolved_workers,
                    thread_name_prefix="heart-rx-input",
                )
                _INPUT_SCHEDULER = ThreadPoolScheduler(_INPUT_EXECUTOR)
    return _INPUT_SCHEDULER
