from __future__ import annotations

from heart.utilities.metrics import (ExponentialMovingAverage, Histogram,
                                     ThresholdCounter)


class TestUtilitiesMetricsHelpers:
    """Group Utilities Metrics Helpers tests so utilities metrics helpers behaviour stays reliable. This preserves confidence in utilities metrics helpers for end-to-end scenarios."""

    def test_histogram_assigns_values_to_correct_bins(self) -> None:
        """Verify that histogram assigns values to correct bins. This supports analytics accuracy for monitoring."""
        histogram: Histogram[str] = Histogram([-1.0, 0.0, 1.0])
        histogram.observe("sensor", -2.0)
        histogram.observe("sensor", -0.5)
        histogram.observe("sensor", 0.5)
        histogram.observe("sensor", 2.0)
        snapshot = histogram.get("sensor")
        assert snapshot["(-inf, -1.0]"] == 1
        assert snapshot["(-1.0, 0.0]"] == 1
        assert snapshot["(0.0, 1.0]"] == 1
        assert snapshot["(1.0, inf)"] == 1



    def test_threshold_counter_tracks_breaches(self) -> None:
        """Verify that threshold counter tracks breaches. This supports analytics accuracy for monitoring."""
        counter: ThresholdCounter[str] = ThresholdCounter(default_threshold=5.0, inclusive=False)
        counter.observe("loop", 5.0)
        counter.observe("loop", 6.0)
        counter.observe("loop", 8.0)
        snapshot = counter.get("loop")
        assert snapshot["breaches"] == 2
        assert snapshot["threshold"] == 5.0



    def test_exponential_moving_average_converges(self) -> None:
        """Verify that exponential moving average converges. This supports analytics accuracy for monitoring."""
        ema: ExponentialMovingAverage[str] = ExponentialMovingAverage(alpha=0.5)
        ema.observe("loop", 0.0)
        ema.observe("loop", 10.0)
        ema.observe("loop", 10.0)
        snapshot = ema.get("loop")
        assert snapshot["ewma"] == 7.5
        assert snapshot["alpha"] == 0.5
