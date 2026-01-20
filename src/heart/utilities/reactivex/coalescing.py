from datetime import timedelta
from typing import Callable

import reactivex
from reactivex.disposable import Disposable

from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import _COALESCE_SCHEDULER, coalesce_scheduler

logger = get_logger(__name__)

CoalesceCallable = Callable[[reactivex.Observable], reactivex.Observable]


class CoalesceBuffer:
    def __init__(self, buffer_time: float, scheduler: reactivex.scheduler.SchedulerBase):
        self._buffer_time = buffer_time
        self._scheduler = scheduler

    def __call__(self, source: reactivex.Observable) -> reactivex.Observable:
        return source.pipe(
            reactivex.operators.buffer_with_time(
                timedelta(milliseconds=self._buffer_time),
                scheduler=self._scheduler,
            ),
            reactivex.operators.filter(lambda buffer: len(buffer) > 0),
        )


def coalesce_latest(buffer_time: float) -> CoalesceCallable:
    """Coalesce emissions within the buffer window into the last value.

    This ensures that downstream processing only receives the most recent value in each
    buffer window, effectively smoothing out high-frequency input streams.
    """

    def coalesce(source: reactivex.Observable) -> reactivex.Observable:
        return source.pipe(
            reactivex.operators.buffer_with_time(
                timedelta(milliseconds=buffer_time),
                scheduler=_COALESCE_SCHEDULER,
            ),
            reactivex.operators.filter(lambda buffer: len(buffer) > 0),
            reactivex.operators.map(lambda buffer: buffer[-1]),
        )

    return coalesce


def coalesce_buffer_with_tracking(
    buffer_time: float,
    scheduler: reactivex.scheduler.SchedulerBase | None = None,
) -> CoalesceCallable:
    """Coalesce emissions within the buffer window into the last value.

    This ensures that downstream processing only receives the most recent value in each
    buffer window, effectively smoothing out high-frequency input streams.
    """

    scheduler = scheduler or coalesce_scheduler()

    def coalesce(source: reactivex.Observable) -> reactivex.Observable:
        def inner() -> tuple[reactivex.Observable, Disposable]:
            buffer: list = []
            buffered = source.subscribe(buffer.append)
            report_handle = scheduler.schedule_relative(
                timedelta(milliseconds=buffer_time),
                lambda *_: logger.debug(
                    "Coalescing buffer has %d entries", len(buffer)
                ),
                state=None,
            )
            return (source, Disposable(lambda: (buffered.dispose(), report_handle.dispose())))

        return reactivex.Observable(inner)

    return coalesce
