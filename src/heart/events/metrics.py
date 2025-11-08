"""Aggregated sensor metrics and reusable event windows."""

from __future__ import annotations

import math
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Generic, Iterable, Iterator, Mapping, TypeVar

T = TypeVar("T")
K = TypeVar("K")


@dataclass(slots=True)
class EventSample(Generic[T]):
    """Timestamped value captured from a sensor."""

    value: T
    timestamp: float


class WindowPolicy(Generic[T]):
    """Strategy for pruning samples held by :class:`EventWindow`."""

    def prune(self, samples: Deque[EventSample[T]], *, now: float) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class MaxLengthPolicy(WindowPolicy[T]):
    """Limit a window to the most recent ``count`` samples."""

    def __init__(self, *, count: int) -> None:
        if count <= 0:
            msg = "count must be a positive integer"
            raise ValueError(msg)
        self._count = count

    def prune(self, samples: Deque[EventSample[T]], *, now: float) -> None:  # noqa: ARG002
        while len(samples) > self._count:
            samples.popleft()


class MaxAgePolicy(WindowPolicy[T]):
    """Limit a window to samples captured within ``window`` seconds."""

    def __init__(self, *, window: float) -> None:
        if window <= 0:
            msg = "window must be a positive duration"
            raise ValueError(msg)
        self._window = window

    def prune(self, samples: Deque[EventSample[T]], *, now: float) -> None:
        cutoff = now - self._window
        while samples and samples[0].timestamp < cutoff:
            samples.popleft()


class EventWindow(Generic[T]):
    """Store the most recent events according to a set of policies."""

    def __init__(self, *, policies: Iterable[WindowPolicy[T]] = ()) -> None:
        self._policies: tuple[WindowPolicy[T], ...] = tuple(policies)
        self._samples: Deque[EventSample[T]] = deque()

    @property
    def policies(self) -> tuple[WindowPolicy[T], ...]:
        return self._policies

    def derive(self, *policies: WindowPolicy[T]) -> "EventWindow[T]":
        """Return a new window with the existing and additional policies."""

        return EventWindow(policies=(*self._policies, *policies))

    def append(self, value: T, *, timestamp: float | None = None) -> None:
        now = time.monotonic() if timestamp is None else timestamp
        self._samples.append(EventSample(value=value, timestamp=now))
        for policy in self._policies:
            policy.prune(self._samples, now=now)

    def extend(self, values: Iterable[T], *, timestamp: float | None = None, step: float = 0.0) -> None:
        """Append multiple values using a shared starting timestamp."""

        now = time.monotonic() if timestamp is None else timestamp
        for index, value in enumerate(values):
            self.append(value, timestamp=now + (index * step))

    def __len__(self) -> int:
        return len(self._samples)

    def __iter__(self) -> Iterator[T]:
        for sample in self._samples:
            yield sample.value

    def samples(self) -> tuple[EventSample[T], ...]:
        return tuple(self._samples)

    def values(self) -> tuple[T, ...]:
        return tuple(sample.value for sample in self._samples)


def combine_windows(*windows: EventWindow[T]) -> EventWindow[T]:
    """Return a new window that enforces the policies from each ``window``."""

    policies: list[WindowPolicy[T]] = []
    for window in windows:
        policies.extend(window.policies)
    return EventWindow(policies=policies)


class LastNEvents(EventWindow[T]):
    """Maintain the last ``count`` events regardless of age."""

    def __init__(self, *, count: int) -> None:
        super().__init__(policies=(MaxLengthPolicy(count=count),))


class LastEventsWithinTimeWindow(EventWindow[T]):
    """Maintain events captured within ``window`` seconds."""

    def __init__(self, *, window: float) -> None:
        super().__init__(policies=(MaxAgePolicy(window=window),))


class LastNEventsWithinTimeWindow(EventWindow[T]):
    """Maintain the last ``count`` events that are newer than ``window`` seconds."""

    def __init__(self, *, count: int, window: float) -> None:
        combined = combine_windows(LastNEvents(count=count), LastEventsWithinTimeWindow(window=window))
        super().__init__(policies=combined.policies)


class CountByKey(Generic[K]):
    """Count observations grouped by ``key``."""

    def __init__(self) -> None:
        self._counts: Counter[K] = Counter()

    def observe(self, key: K, *, amount: int = 1) -> None:
        self._counts[key] += amount

    def get(self, key: K) -> int:
        return self._counts.get(key, 0)

    def snapshot(self) -> Mapping[K, int]:
        return dict(self._counts)

    def reset(self) -> None:
        self._counts.clear()


@dataclass(slots=True)
class RollingSnapshot:
    """Point-in-time view of rolling statistics for a single key."""

    count: int
    mean: float | None
    stddev: float | None


class _RollingState:
    __slots__ = ("samples", "sum", "sum_sq")

    def __init__(self) -> None:
        self.samples: Deque[EventSample[float]] = deque()
        self.sum = 0.0
        self.sum_sq = 0.0

    def append(self, value: float, *, timestamp: float, maxlen: int | None, window: float | None) -> None:
        sample = EventSample(value=value, timestamp=timestamp)
        self.samples.append(sample)
        self.sum += value
        self.sum_sq += value * value
        self._prune(now=timestamp, maxlen=maxlen, window=window)

    def _prune(self, *, now: float, maxlen: int | None, window: float | None) -> None:
        if window is not None:
            cutoff = now - window
            while self.samples and self.samples[0].timestamp < cutoff:
                removed = self.samples.popleft()
                self.sum -= removed.value
                self.sum_sq -= removed.value * removed.value

        if maxlen is not None:
            while len(self.samples) > maxlen:
                removed = self.samples.popleft()
                self.sum -= removed.value
                self.sum_sq -= removed.value * removed.value

    def snapshot(self) -> RollingSnapshot:
        count = len(self.samples)
        if count == 0:
            return RollingSnapshot(count=0, mean=None, stddev=None)

        mean = self.sum / count
        variance = (self.sum_sq / count) - (mean * mean)
        variance = max(0.0, variance)
        stddev = math.sqrt(variance) if count > 1 else None
        return RollingSnapshot(count=count, mean=mean, stddev=stddev)


class RollingStatisticsByKey(Generic[K]):
    """Compute rolling statistics for float samples grouped by key."""

    def __init__(self, *, maxlen: int | None = None, window: float | None = None) -> None:
        if maxlen is not None and maxlen <= 0:
            msg = "maxlen must be a positive integer"
            raise ValueError(msg)
        if window is not None and window <= 0:
            msg = "window must be a positive duration"
            raise ValueError(msg)
        self._maxlen = maxlen
        self._window = window
        self._states: Dict[K, _RollingState] = defaultdict(_RollingState)

    def observe(self, key: K, value: float, *, timestamp: float | None = None) -> None:
        now = time.monotonic() if timestamp is None else timestamp
        state = self._states[key]
        state.append(float(value), timestamp=now, maxlen=self._maxlen, window=self._window)

    def mean(self, key: K) -> float | None:
        snapshot = self._states.get(key)
        if snapshot is None:
            return None
        return snapshot.snapshot().mean

    def stddev(self, key: K) -> float | None:
        snapshot = self._states.get(key)
        if snapshot is None:
            return None
        return snapshot.snapshot().stddev

    def count(self, key: K) -> int:
        snapshot = self._states.get(key)
        if snapshot is None:
            return 0
        return snapshot.snapshot().count

    def snapshot(self) -> Mapping[K, RollingSnapshot]:
        return {key: state.snapshot() for key, state in self._states.items()}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._states.clear()
            return
        self._states.pop(key, None)


class RollingAverageByKey(Generic[K]):
    """Rolling mean of float samples grouped by key."""

    def __init__(self, *, maxlen: int | None = None, window: float | None = None) -> None:
        self._stats = RollingStatisticsByKey[K](maxlen=maxlen, window=window)

    def observe(self, key: K, value: float, *, timestamp: float | None = None) -> None:
        self._stats.observe(key, value, timestamp=timestamp)

    def get(self, key: K) -> float | None:
        return self._stats.mean(key)

    def snapshot(self) -> Mapping[K, float | None]:
        return {key: snap.mean for key, snap in self._stats.snapshot().items()}

    def reset(self, key: K | None = None) -> None:
        self._stats.reset(key)


class RollingMeanByKey(RollingAverageByKey[K]):
    """Alias for :class:`RollingAverageByKey`."""


class RollingStddevByKey(Generic[K]):
    """Rolling standard deviation of float samples grouped by key."""

    def __init__(self, *, maxlen: int | None = None, window: float | None = None) -> None:
        self._stats = RollingStatisticsByKey[K](maxlen=maxlen, window=window)

    def observe(self, key: K, value: float, *, timestamp: float | None = None) -> None:
        self._stats.observe(key, value, timestamp=timestamp)

    def get(self, key: K) -> float | None:
        return self._stats.stddev(key)

    def snapshot(self) -> Mapping[K, float | None]:
        return {key: snap.stddev for key, snap in self._stats.snapshot().items()}

    def reset(self, key: K | None = None) -> None:
        self._stats.reset(key)


__all__ = [
    "CountByKey",
    "EventSample",
    "EventWindow",
    "LastEventsWithinTimeWindow",
    "LastNEvents",
    "LastNEventsWithinTimeWindow",
    "MaxAgePolicy",
    "MaxLengthPolicy",
    "RollingAverageByKey",
    "RollingMeanByKey",
    "RollingSnapshot",
    "RollingStatisticsByKey",
    "RollingStddevByKey",
    "combine_windows",
]
