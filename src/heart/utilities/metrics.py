"""Utility metric helpers supporting keyed-metric implementations."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Mapping, Sequence, TypeVar

from heart.events.metrics import KeyedMetric

K = TypeVar("K")


def _format_bucket(lower: float | None, upper: float | None) -> str:
    if lower is None and upper is None:
        return "(-inf, inf)"
    if lower is None:
        return f"(-inf, {upper}]"
    if upper is None:
        return f"({lower}, inf)"
    return f"({lower}, {upper}]"


class Histogram(KeyedMetric[K, Mapping[str, int]]):
    """Bucket scalar samples into histogram bins per key."""

    def __init__(self, buckets: Sequence[float]) -> None:
        if not buckets:
            msg = "buckets must be a non-empty sequence"
            raise ValueError(msg)
        sorted_edges = sorted(float(boundary) for boundary in buckets)
        self._edges = tuple(sorted_edges)
        labels: list[str] = []
        previous: float | None = None
        for boundary in self._edges:
            labels.append(_format_bucket(previous, boundary))
            previous = boundary
        labels.append(_format_bucket(previous, None))
        self._labels = tuple(labels)
        self._counts: Dict[K, list[int]] = {}

    def _ensure_counts(self, key: K) -> list[int]:
        counts = self._counts.get(key)
        if counts is None:
            counts = [0 for _ in self._labels]
            self._counts[key] = counts
        return counts

    def observe(self, key: K, value: float, /) -> None:
        counts = self._ensure_counts(key)
        index = bisect_right(self._edges, float(value))
        counts[index] += 1

    def get(self, key: K) -> Mapping[str, int]:
        counts = self._counts.get(key)
        if counts is None:
            return {label: 0 for label in self._labels}
        return dict(zip(self._labels, counts, strict=True))

    def snapshot(self) -> Mapping[K, Mapping[str, int]]:
        return {key: dict(zip(self._labels, counts, strict=True)) for key, counts in self._counts.items()}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._counts.clear()
            return
        self._counts.pop(key, None)


class ThresholdCounter(KeyedMetric[K, Mapping[str, float | int]]):
    """Count threshold exceedances per key."""

    def __init__(self, *, default_threshold: float, inclusive: bool = True) -> None:
        self._default_threshold = float(default_threshold)
        self._inclusive = inclusive
        self._counts: Dict[K, int] = defaultdict(int)
        self._thresholds: Dict[K, float] = {}

    def observe(self, key: K, value: float, *, threshold: float | None = None) -> None:
        if threshold is not None:
            self._thresholds[key] = float(threshold)
        limit = self._thresholds.get(key, self._default_threshold)
        exceeds = value >= limit if self._inclusive else value > limit
        if exceeds:
            self._counts[key] += 1

    def get(self, key: K) -> Mapping[str, float | int]:
        threshold = self._thresholds.get(key, self._default_threshold)
        return {"breaches": self._counts.get(key, 0), "threshold": threshold}

    def snapshot(self) -> Mapping[K, Mapping[str, float | int]]:
        keys = set(self._counts) | set(self._thresholds)
        return {key: self.get(key) for key in keys}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._counts.clear()
            self._thresholds.clear()
            return
        self._counts.pop(key, None)
        self._thresholds.pop(key, None)


class ExponentialMovingAverage(KeyedMetric[K, Mapping[str, float]]):
    """Compute an exponential moving average for each key."""

    def __init__(self, alpha: float) -> None:
        if not 0.0 < alpha <= 1.0:
            msg = "alpha must be in the interval (0, 1]"
            raise ValueError(msg)
        self._alpha = alpha
        self._state: Dict[K, float] = {}

    @property
    def alpha(self) -> float:
        return self._alpha

    def observe(self, key: K, value: float) -> None:
        previous = self._state.get(key)
        if previous is None:
            self._state[key] = float(value)
        else:
            self._state[key] = (self._alpha * float(value)) + ((1.0 - self._alpha) * previous)

    def get(self, key: K) -> Mapping[str, float]:
        value = self._state.get(key)
        if value is None:
            return {"ewma": 0.0, "alpha": self._alpha}
        return {"ewma": value, "alpha": self._alpha}

    def snapshot(self) -> Mapping[K, Mapping[str, float]]:
        return {key: {"ewma": value, "alpha": self._alpha} for key, value in self._state.items()}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._state.clear()
            return
        self._state.pop(key, None)


@dataclass(slots=True)
class RollingSumSnapshot:
    total: float
    count: int


class RollingSum(KeyedMetric[K, RollingSumSnapshot]):
    """Maintain rolling sums per key with optional normalisation."""

    def __init__(self) -> None:
        self._totals: Dict[K, float] = defaultdict(float)
        self._counts: Dict[K, int] = defaultdict(int)

    def observe(self, key: K, value: float) -> None:
        self._totals[key] += float(value)
        self._counts[key] += 1

    def get(self, key: K) -> RollingSumSnapshot:
        return RollingSumSnapshot(total=self._totals.get(key, 0.0), count=self._counts.get(key, 0))

    def snapshot(self) -> Mapping[K, RollingSumSnapshot]:
        keys = set(self._totals) | set(self._counts)
        return {key: RollingSumSnapshot(total=self._totals.get(key, 0.0), count=self._counts.get(key, 0)) for key in keys}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._totals.clear()
            self._counts.clear()
            return
        self._totals.pop(key, None)
        self._counts.pop(key, None)
