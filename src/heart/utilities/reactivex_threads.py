from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from reactivex.scheduler import ThreadPoolScheduler

_SCHEDULER_LOCK = Lock()
_SCHEDULER: ThreadPoolScheduler | None = None
_EXECUTOR: ThreadPoolExecutor | None = None


def background_scheduler(max_workers: int = 4) -> ThreadPoolScheduler:
    """Return the shared scheduler for background reactivex work."""
    global _SCHEDULER, _EXECUTOR
    if _SCHEDULER is None:
        with _SCHEDULER_LOCK:
            if _SCHEDULER is None:
                _EXECUTOR = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix="heart-rx",
                )
                _SCHEDULER = ThreadPoolScheduler(_EXECUTOR)
    return _SCHEDULER
