"""Statistical helpers backing advanced metric calculations."""

from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

import numpy as np


def geometric_mean(values: Sequence[float]) -> float:
    """Return the geometric mean of ``values``."""

    array = np.asarray(values, dtype=float)
    if array.size == 0:
        msg = "values must contain at least one element"
        raise ValueError(msg)
    if np.any(array <= 0):
        msg = "geometric mean is undefined for non-positive values"
        raise ValueError(msg)
    return float(np.exp(np.mean(np.log(array))))


def sample_entropy(values: Sequence[float], *, m: int = 2, r: float | None = None) -> float:
    """Compute sample entropy for a one-dimensional series."""

    array = np.asarray(values, dtype=float)
    if array.size <= m + 1:
        msg = "values must contain more samples than embedding dimension"
        raise ValueError(msg)
    if r is None:
        r = 0.2 * np.std(array)
    count_m = 0
    count_m1 = 0
    for i in range(array.size - m):
        template = array[i : i + m]
        for j in range(i + 1, array.size - m):
            comparison = array[j : j + m]
            if np.max(np.abs(template - comparison)) <= r:
                count_m += 1
                if abs(array[i + m] - array[j + m]) <= r:
                    count_m1 += 1
    if count_m == 0 or count_m1 == 0:
        return float("inf")
    return float(-np.log(count_m1 / count_m))


def permutation_entropy(values: Sequence[float], *, order: int = 3, delay: int = 1) -> float:
    """Compute permutation entropy for ``values``."""

    array = np.asarray(values, dtype=float)
    if order < 2:
        msg = "order must be at least 2"
        raise ValueError(msg)
    if delay < 1:
        msg = "delay must be positive"
        raise ValueError(msg)
    n_patterns = array.size - (order - 1) * delay
    if n_patterns <= 0:
        msg = "values must contain enough samples for the requested order"
        raise ValueError(msg)
    patterns = []
    for i in range(n_patterns):
        window = array[i : i + order * delay : delay]
        pattern = tuple(np.argsort(window))
        patterns.append(pattern)
    counts = Counter(patterns)
    probabilities = np.array([count / len(patterns) for count in counts.values()])
    entropy = -np.sum(probabilities * np.log(probabilities))
    return float(entropy / np.log(math.factorial(order)))


def hurst_exponent(values: Sequence[float], *, min_window: int = 8, max_window: int = 128) -> float:
    """Estimate the Hurst exponent using rescaled range analysis."""

    array = np.asarray(values, dtype=float)
    if array.size < max_window:
        msg = "values must contain at least ``max_window`` samples"
        raise ValueError(msg)
    window_sizes = []
    rs_values = []
    for window in range(min_window, max_window + 1):
        if window >= array.size:
            break
        segments = array[: array.size - (array.size % window)].reshape(-1, window)
        rs_segment: list[float] = []
        for segment in segments:
            mean = segment.mean()
            dev = segment - mean
            cumulative = np.cumsum(dev)
            range_ = cumulative.max() - cumulative.min()
            std = segment.std()
            if std == 0:
                continue
            rs_segment.append(range_ / std)
        if not rs_segment:
            continue
        rs_values.append(np.mean(rs_segment))
        window_sizes.append(window)
    if len(rs_values) < 2:
        return 0.5
    log_windows = np.log(window_sizes)
    log_rs = np.log(rs_values)
    slope, _ = np.polyfit(log_windows, log_rs, 1)
    return float(slope)
