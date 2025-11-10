from __future__ import annotations

import numpy as np
import pytest

from heart.events.metrics import (InterArrivalMetric, MomentMetric,
                                  PercentileMetric, RollingExtrema)


class TestEventsMetricsAdvancedMetrics:
    """Group Events Metrics Advanced Metrics tests so events metrics advanced metrics behaviour stays reliable. This preserves confidence in events metrics advanced metrics for end-to-end scenarios."""

    def test_rolling_extrema_respects_maxlen(self) -> None:
        """Verify that RollingExtrema evicts older samples once the maximum window length is reached. This keeps memory bounded so real-time analytics stay performant."""
        metric: RollingExtrema[str] = RollingExtrema(maxlen=2)
        metric.observe("loop", 10.0, timestamp=0.0)
        metric.observe("loop", 5.0, timestamp=1.0)
        metric.observe("loop", 8.0, timestamp=2.0)
        snapshot = metric.get("loop")
        assert snapshot == {"min": 5.0, "max": 8.0}



    def test_percentile_metric_matches_numpy(self) -> None:
        """Verify that PercentileMetric reports the same percentile estimates as NumPy's linear interpolation. This validates our calculation pipeline against a trusted reference to avoid statistical drift."""
        samples = [1.0, 2.0, 3.0, 4.0, 5.0]
        metric: PercentileMetric[str] = PercentileMetric((50.0, 90.0))
        for index, sample in enumerate(samples):
            metric.observe("sensor", sample, timestamp=float(index))
        snapshot = metric.get("sensor")
        expected = np.percentile(np.array(samples), (50.0, 90.0), method="linear")
        assert snapshot["p50"] == expected[0]
        assert snapshot["p90"] == expected[1]



    def test_interarrival_metric_limits_window(self) -> None:
        """Verify that InterArrivalMetric keeps only the latest arrival intervals within the configured window size. This keeps latency reporting focused on current behaviour for alerting accuracy."""
        metric: InterArrivalMetric[str] = InterArrivalMetric(maxlen=2)
        metric.observe("imu", timestamp=0.0)
        metric.observe("imu", timestamp=0.1)
        metric.observe("imu", timestamp=0.25)
        metric.observe("imu", timestamp=0.4)
        snapshot = metric.get("imu")
        assert snapshot["interval_ms"] == pytest.approx((150.0, 150.0))



    def test_moment_metric_normalises_kurtosis(self) -> None:
        """Verify that MomentMetric returns a normalised kurtosis value when normalisation is enabled. This ensures comparisons across channels remain meaningful when data scales differ."""
        samples = [1.0, 2.0, 3.0, 4.0]
        metric: MomentMetric[str] = MomentMetric(order=4, label="kurtosis", normalise=True)
        for index, sample in enumerate(samples):
            metric.observe("channel", sample, timestamp=float(index))
        snapshot = metric.get("channel")
        array = np.array(samples)
        centred = array - array.mean()
        expected = float(np.mean(np.power(centred, 4)) / (np.std(array) ** 4))
        assert snapshot["kurtosis"] == expected
