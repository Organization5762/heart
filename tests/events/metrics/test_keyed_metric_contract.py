"""Regression coverage for the :class:`KeyedMetric` scaffolding."""

from __future__ import annotations

import pytest

from heart.events.metrics import CountByKey, KeyedMetric, RollingAverageByKey


class TestEventsMetricsKeyedMetricContract:
    """Group Events Metrics Keyed Metric Contract tests so events metrics keyed metric contract behaviour stays reliable. This preserves confidence in events metrics keyed metric contract for end-to-end scenarios."""

    def test_count_by_key_obeys_keyed_metric_contract(self) -> None:
        """Verify that CountByKey satisfies the KeyedMetric contract for observation, snapshot, and reset. This ensures the base interface remains backward compatible for metric implementations."""
        metric: KeyedMetric[str, int] = CountByKey[str]()

        assert isinstance(metric, KeyedMetric)

        metric.observe("imu", amount=2)
        metric.observe("imu", amount=3)

        assert metric.get("imu") == 5

        snapshot = metric.snapshot()
        snapshot["imu"] = 0

        assert metric.get("imu") == 5

        metric.reset("imu")
        assert metric.get("imu") == 0

        metric.observe("imu", amount=7)
        metric.reset()

        assert metric.get("imu") == 0



    def test_rolling_average_keyed_metric_example(self) -> None:
        """Verify that RollingAverageByKey exercises the KeyedMetric workflow for averaging values. This demonstrates how temporal metrics can rely on the shared lifecycle to stay consistent."""
        metric: KeyedMetric[str, float | None] = RollingAverageByKey[str](maxlen=2)

        metric.observe("imu", 5.0, timestamp=0.0)
        metric.observe("imu", 7.0, timestamp=1.0)

        assert metric.get("imu") == pytest.approx(6.0)

        snapshot = metric.snapshot()
        snapshot["imu"] = None

        assert metric.get("imu") == pytest.approx(6.0)

        metric.reset("imu")
        assert metric.get("imu") is None

        metric.observe("imu", 9.0, timestamp=2.0)
        metric.reset()

        assert metric.get("imu") is None
