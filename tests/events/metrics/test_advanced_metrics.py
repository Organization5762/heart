from __future__ import annotations

import numpy as np
import pytest

from heart.events.metrics import (InterArrivalMetric, MomentMetric,
                                  PercentileMetric, RollingExtrema)


def test_rolling_extrema_respects_maxlen() -> None:
    metric: RollingExtrema[str] = RollingExtrema(maxlen=2)
    metric.observe("loop", 10.0, timestamp=0.0)
    metric.observe("loop", 5.0, timestamp=1.0)
    metric.observe("loop", 8.0, timestamp=2.0)
    snapshot = metric.get("loop")
    assert snapshot == {"min": 5.0, "max": 8.0}


def test_percentile_metric_matches_numpy() -> None:
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    metric: PercentileMetric[str] = PercentileMetric((50.0, 90.0))
    for index, sample in enumerate(samples):
        metric.observe("sensor", sample, timestamp=float(index))
    snapshot = metric.get("sensor")
    expected = np.percentile(np.array(samples), (50.0, 90.0), method="linear")
    assert snapshot["p50"] == expected[0]
    assert snapshot["p90"] == expected[1]


def test_interarrival_metric_limits_window() -> None:
    metric: InterArrivalMetric[str] = InterArrivalMetric(maxlen=2)
    metric.observe("imu", timestamp=0.0)
    metric.observe("imu", timestamp=0.1)
    metric.observe("imu", timestamp=0.25)
    metric.observe("imu", timestamp=0.4)
    snapshot = metric.get("imu")
    assert snapshot["interval_ms"] == pytest.approx((150.0, 150.0))


def test_moment_metric_normalises_kurtosis() -> None:
    samples = [1.0, 2.0, 3.0, 4.0]
    metric: MomentMetric[str] = MomentMetric(order=4, label="kurtosis", normalise=True)
    for index, sample in enumerate(samples):
        metric.observe("channel", sample, timestamp=float(index))
    snapshot = metric.get("channel")
    array = np.array(samples)
    centred = array - array.mean()
    expected = float(np.mean(np.power(centred, 4)) / (np.std(array) ** 4))
    assert snapshot["kurtosis"] == expected
