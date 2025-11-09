"""Aggregated sensor metrics and reusable event windows.

The helpers in this module are deliberately small and composable so that new
metrics can be introduced without duplicating bookkeeping logic.  Most keyed
metrics in the code base expose a shared interface consisting of four methods:

``observe``
    Accept a new input sample for a key.  The exact arguments depend on the
    metric (for example, a count metric records an amount while a rolling
    average records a numeric value), but every implementation must store the
    observation without mutating previously returned snapshots.

``get``
    Return the current aggregated value for a single key.  Implementations may
    return ``None`` when no value has been observed yet or when the internal
    window has been pruned.

``snapshot``
    Produce a defensive mapping of keys to their aggregate value.  The return
    type should be safe to hand to callers without exposing internal state.

``reset``
    Clear data for either a specific key or the entire metric when ``key`` is
    omitted.  Resetting must not raise when the key is unknown.

The :class:`KeyedMetric` abstract base class below captures these conventions so
that new metrics can inherit ready-made documentation and tooling support.
"""

from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import (Any, Deque, Dict, Generic, Iterable, Iterator, Mapping,
                    Sequence, TypeVar)

import numpy as np

T = TypeVar("T")
K = TypeVar("K")
ValueT_co = TypeVar("ValueT_co", covariant=True)


class KeyedMetric(Generic[K, ValueT_co], ABC):
    """Interface describing the lifecycle of keyed aggregate metrics.

    Subclasses must implement the four primitive operations documented in the
    module docstring.  The signatures intentionally accept ``*args`` and
    ``**kwargs`` so that a wide variety of metrics (counters, averages, rolling
    statistics, etc.) can share the same base type while exposing
    metric-specific inputs.

    When overriding ``snapshot`` the returned mapping *must* be detached from
    any internal mutable state.  Returning ``dict(...)`` or a tuple-backed
    mapping keeps callers from mutating the metric by accident.  Likewise,
    ``reset`` implementations should tolerate unknown keys so that callers can
    treat the method as idempotent.
    """

    @abstractmethod
    def observe(self, key: K, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - interface
        """Record a new observation for ``key``."""

    @abstractmethod
    def get(self, key: K) -> ValueT_co:  # pragma: no cover - interface
        """Return the current aggregate for ``key``."""

    @abstractmethod
    def snapshot(self) -> Mapping[K, ValueT_co]:  # pragma: no cover - interface
        """Return a point-in-time mapping of all aggregates."""

    @abstractmethod
    def reset(self, key: K | None = None) -> None:  # pragma: no cover - interface
        """Clear stored observations for ``key`` or every key when omitted."""


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
        while samples and samples[0].timestamp <= cutoff:
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


class CountByKey(KeyedMetric[K, int]):
    """Count observations grouped by ``key``."""

    def __init__(self) -> None:
        self._counts: Counter[K] = Counter()

    def observe(self, key: K, *, amount: int = 1) -> None:
        self._counts[key] += amount

    def get(self, key: K) -> int:
        return self._counts.get(key, 0)

    def snapshot(self) -> Mapping[K, int]:
        return dict(self._counts)

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._counts.clear()
            return
        self._counts.pop(key, None)


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
            while self.samples and self.samples[0].timestamp <= cutoff:
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


class RollingExtrema(KeyedMetric[K, Mapping[str, float | None]]):
    """Track rolling minima and maxima for float samples grouped by key."""

    def __init__(self, *, maxlen: int | None = None, window: float | None = None) -> None:
        if maxlen is not None and maxlen <= 0:
            msg = "maxlen must be a positive integer"
            raise ValueError(msg)
        if window is not None and window <= 0:
            msg = "window must be a positive duration"
            raise ValueError(msg)
        self._maxlen = maxlen
        self._window = window
        self._windows: Dict[K, EventWindow[float]] = {}

    def _make_window(self) -> EventWindow[float]:
        policies: list[WindowPolicy[float]] = []
        if self._maxlen is not None:
            policies.append(MaxLengthPolicy(count=self._maxlen))
        if self._window is not None:
            policies.append(MaxAgePolicy(window=self._window))
        return EventWindow(policies=policies)

    def observe(self, key: K, value: float, *, timestamp: float | None = None) -> None:
        now = time.monotonic() if timestamp is None else timestamp
        window = self._windows.get(key)
        if window is None:
            window = self._make_window()
            self._windows[key] = window
        window.append(float(value), timestamp=now)

    def get(self, key: K) -> Mapping[str, float | None]:
        window = self._windows.get(key)
        if window is None or len(window) == 0:
            return {"min": None, "max": None}
        values = window.values()
        return {"min": min(values), "max": max(values)}

    def snapshot(self) -> Mapping[K, Mapping[str, float | None]]:
        return {key: self.get(key) for key in self._windows}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._windows.clear()
            return
        self._windows.pop(key, None)


class PercentileMetric(KeyedMetric[K, Mapping[str, float | None]]):
    """Compute rolling percentiles for float samples grouped by key."""

    def __init__(
        self,
        percentiles: Sequence[float],
        *,
        maxlen: int | None = None,
        window: float | None = None,
        method: str = "linear",
    ) -> None:
        if not percentiles:
            msg = "percentiles must be a non-empty sequence"
            raise ValueError(msg)
        for percentile in percentiles:
            if percentile < 0 or percentile > 100:
                msg = "percentiles must be within [0, 100]"
                raise ValueError(msg)
        if maxlen is not None and maxlen <= 0:
            msg = "maxlen must be a positive integer"
            raise ValueError(msg)
        if window is not None and window <= 0:
            msg = "window must be a positive duration"
            raise ValueError(msg)
        self._percentiles = tuple(percentiles)
        self._labels = tuple(f"p{int(percentile)}" if percentile.is_integer() else f"p{percentile}" for percentile in self._percentiles)
        self._method = method
        self._maxlen = maxlen
        self._window = window
        self._windows: Dict[K, EventWindow[float]] = {}

    def _make_window(self) -> EventWindow[float]:
        policies: list[WindowPolicy[float]] = []
        if self._maxlen is not None:
            policies.append(MaxLengthPolicy(count=self._maxlen))
        if self._window is not None:
            policies.append(MaxAgePolicy(window=self._window))
        return EventWindow(policies=policies)

    def observe(self, key: K, value: float, *, timestamp: float | None = None) -> None:
        now = time.monotonic() if timestamp is None else timestamp
        window = self._windows.get(key)
        if window is None:
            window = self._make_window()
            self._windows[key] = window
        window.append(float(value), timestamp=now)

    def _percentile_snapshot(self, window: EventWindow[float]) -> Mapping[str, float | None]:
        if len(window) == 0:
            return {label: None for label in self._labels}
        values = np.array(window.values(), dtype=float)
        quantiles = np.percentile(values, self._percentiles, method=self._method)
        return {label: float(value) for label, value in zip(self._labels, quantiles)}

    def get(self, key: K) -> Mapping[str, float | None]:
        window = self._windows.get(key)
        if window is None:
            return {label: None for label in self._labels}
        return self._percentile_snapshot(window)

    def snapshot(self) -> Mapping[K, Mapping[str, float | None]]:
        return {key: self._percentile_snapshot(window) for key, window in self._windows.items()}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._windows.clear()
            return
        self._windows.pop(key, None)


class MomentMetric(KeyedMetric[K, Mapping[str, float | None]]):
    """Compute rolling central moments for float samples grouped by key."""

    def __init__(
        self,
        order: int,
        *,
        label: str = "moment",
        maxlen: int | None = None,
        window: float | None = None,
        normalise: bool = False,
    ) -> None:
        if order <= 0:
            msg = "order must be a positive integer"
            raise ValueError(msg)
        if maxlen is not None and maxlen <= 0:
            msg = "maxlen must be a positive integer"
            raise ValueError(msg)
        if window is not None and window <= 0:
            msg = "window must be a positive duration"
            raise ValueError(msg)
        self._order = order
        self._label = label
        self._normalise = normalise
        self._maxlen = maxlen
        self._window = window
        self._windows: Dict[K, EventWindow[float]] = {}

    def _make_window(self) -> EventWindow[float]:
        policies: list[WindowPolicy[float]] = []
        if self._maxlen is not None:
            policies.append(MaxLengthPolicy(count=self._maxlen))
        if self._window is not None:
            policies.append(MaxAgePolicy(window=self._window))
        return EventWindow(policies=policies)

    def observe(self, key: K, value: float, *, timestamp: float | None = None) -> None:
        now = time.monotonic() if timestamp is None else timestamp
        window = self._windows.get(key)
        if window is None:
            window = self._make_window()
            self._windows[key] = window
        window.append(float(value), timestamp=now)

    def _moment_snapshot(self, window: EventWindow[float]) -> Mapping[str, float | None]:
        if len(window) == 0:
            return {self._label: None}
        values = np.array(window.values(), dtype=float)
        mean = float(np.mean(values))
        centred = values - mean
        moment = float(np.mean(np.power(centred, self._order)))
        if self._normalise:
            std = float(np.std(values))
            if std > 0.0:
                moment /= std**self._order
        return {self._label: moment}

    def get(self, key: K) -> Mapping[str, float | None]:
        window = self._windows.get(key)
        if window is None:
            return {self._label: None}
        return self._moment_snapshot(window)

    def snapshot(self) -> Mapping[K, Mapping[str, float | None]]:
        return {key: self._moment_snapshot(window) for key, window in self._windows.items()}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._windows.clear()
            return
        self._windows.pop(key, None)


class InterArrivalMetric(KeyedMetric[K, Mapping[str, tuple[float, ...]]]):
    """Capture per-key inter-arrival intervals to monitor cadence drift."""

    def __init__(self, *, maxlen: int | None = None) -> None:
        if maxlen is not None and maxlen <= 0:
            msg = "maxlen must be a positive integer"
            raise ValueError(msg)
        self._maxlen = maxlen
        self._intervals: Dict[K, Deque[float]] = defaultdict(deque)
        self._last_timestamp: Dict[K, float] = {}

    def observe(self, key: K, *, timestamp: float | None = None) -> None:
        now = time.monotonic() if timestamp is None else timestamp
        last = self._last_timestamp.get(key)
        if last is not None:
            interval_ms = max(0.0, (now - last) * 1000.0)
            deque_ = self._intervals[key]
            deque_.append(interval_ms)
            if self._maxlen is not None:
                while len(deque_) > self._maxlen:
                    deque_.popleft()
        self._last_timestamp[key] = now

    def get(self, key: K) -> Mapping[str, tuple[float, ...]]:
        intervals = self._intervals.get(key, deque())
        if not intervals:
            return {"interval_ms": ()}
        return {"interval_ms": tuple(intervals)}

    def snapshot(self) -> Mapping[K, Mapping[str, tuple[float, ...]]]:
        return {key: {"interval_ms": tuple(intervals)} for key, intervals in self._intervals.items()}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._intervals.clear()
            self._last_timestamp.clear()
            return
        self._intervals.pop(key, None)
        self._last_timestamp.pop(key, None)


class RollingAverageByKey(KeyedMetric[K, float | None]):
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


class RollingStddevByKey(KeyedMetric[K, float | None]):
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
