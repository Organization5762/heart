from __future__ import annotations

from heart.utilities.metrics import (ExponentialMovingAverage, Histogram,
                                     ThresholdCounter)


def test_histogram_assigns_values_to_correct_bins() -> None:
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


def test_threshold_counter_tracks_breaches() -> None:
    counter: ThresholdCounter[str] = ThresholdCounter(default_threshold=5.0, inclusive=False)
    counter.observe("loop", 5.0)
    counter.observe("loop", 6.0)
    counter.observe("loop", 8.0)
    snapshot = counter.get("loop")
    assert snapshot["breaches"] == 2
    assert snapshot["threshold"] == 5.0


def test_exponential_moving_average_converges() -> None:
    ema: ExponentialMovingAverage[str] = ExponentialMovingAverage(alpha=0.5)
    ema.observe("loop", 0.0)
    ema.observe("loop", 10.0)
    ema.observe("loop", 10.0)
    snapshot = ema.get("loop")
    assert snapshot["ewma"] == 7.5
    assert snapshot["alpha"] == 0.5
