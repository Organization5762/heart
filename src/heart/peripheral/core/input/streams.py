from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from manyfold.architecture import PubSubObservable

from heart.peripheral.core.input.frame import FrameTick
from heart.peripheral.core.variables import Variable

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class _SampleAverage:
    elapsed_ms: float = 0.0
    total: float = 0.0
    samples: int = 0
    value: float | None = None


def map_stream(source: Variable[T], mapper: Callable[[T], U]) -> Variable[U]:
    return source.map(mapper)


def merge_streams(*streams: Variable[T]) -> Variable[T]:
    return PubSubObservable.merge(*streams)


def average_by_frame_window(
    source: Variable[T | None],
    frame_ticks: Variable[FrameTick],
    *,
    interval_ms: float,
    selector: Callable[[T], float],
) -> Variable[float]:
    def accumulate(previous: _SampleAverage, latest: tuple[FrameTick, T | None]):
        frame_tick, value = latest
        elapsed_ms = previous.elapsed_ms + max(float(frame_tick.delta_ms), 0.0)
        total = previous.total
        samples = previous.samples
        if value is not None:
            total += selector(value)
            samples += 1
        if elapsed_ms < interval_ms:
            return _SampleAverage(
                elapsed_ms=elapsed_ms,
                total=total,
                samples=samples,
            )
        average = None if samples == 0 else total / float(samples)
        return _SampleAverage(value=average)

    return (
        frame_ticks.with_latest_from(source)
        .scan(accumulate, seed=_SampleAverage())
        .filter(lambda average: average.value is not None)
        .map(lambda average: average.value)
    )


def threshold_direction(value: float, threshold: float) -> int:
    if value >= threshold:
        return 1
    if value <= -threshold:
        return -1
    return 0
