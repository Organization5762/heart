"""Tests for rolling statistics helpers grouped by key."""

from __future__ import annotations

import math

import pytest

from heart.events.metrics import (RollingAverageByKey, RollingMeanByKey,
                                  RollingStatisticsByKey, RollingStddevByKey)


def test_rolling_statistics_tracks_multiple_keys() -> None:
    stats = RollingStatisticsByKey[str](maxlen=3)

    stats.observe("imu", 1.0, timestamp=0.0)
    stats.observe("imu", 3.0, timestamp=1.0)
    stats.observe("imu", 5.0, timestamp=2.0)
    stats.observe("imu", 7.0, timestamp=3.0)
    stats.observe("heart", 60.0, timestamp=3.0)
    stats.observe("heart", 70.0, timestamp=4.0)

    imu = stats.snapshot()["imu"]
    heart = stats.snapshot()["heart"]

    assert imu.count == 3
    assert imu.mean == pytest.approx(5.0)
    assert imu.stddev == pytest.approx(math.sqrt(8 / 3))
    assert heart.count == 2
    assert heart.mean == pytest.approx(65.0)
    assert heart.stddev == pytest.approx(5.0)


def test_rolling_statistics_prunes_by_window_and_length() -> None:
    stats = RollingStatisticsByKey[str](maxlen=3, window=5.0)

    stats.observe("imu", 1.0, timestamp=0.0)
    stats.observe("imu", 3.0, timestamp=1.0)
    stats.observe("imu", 5.0, timestamp=2.0)
    stats.observe("imu", 7.0, timestamp=9.0)

    snapshot = stats.snapshot()["imu"]
    assert snapshot.count == 1
    assert snapshot.mean == pytest.approx(7.0)


def test_rolling_statistics_handles_missing_keys() -> None:
    stats = RollingStatisticsByKey[str]()

    assert stats.mean("missing") is None
    assert stats.stddev("missing") is None
    assert stats.count("missing") == 0


def test_rolling_statistics_reset_scopes() -> None:
    stats = RollingStatisticsByKey[str]()

    stats.observe("imu", 1.0, timestamp=0.0)
    stats.observe("imu", 3.0, timestamp=1.0)
    stats.observe("heart", 60.0, timestamp=1.0)

    stats.reset("imu")
    assert "imu" not in stats.snapshot()
    assert "heart" in stats.snapshot()

    stats.reset()
    assert stats.snapshot() == {}


def test_rolling_average_and_stddev_wrappers() -> None:
    averages = RollingAverageByKey[str](maxlen=2)
    deviations = RollingStddevByKey[str](maxlen=2)

    averages.observe("imu", 5.0, timestamp=0.0)
    deviations.observe("imu", 5.0, timestamp=0.0)
    averages.observe("imu", 9.0, timestamp=1.0)
    deviations.observe("imu", 9.0, timestamp=1.0)

    assert averages.get("imu") == pytest.approx(7.0)
    assert deviations.get("imu") == pytest.approx(2.0)
    assert averages.snapshot()["imu"] == pytest.approx(7.0)
    assert deviations.snapshot()["imu"] == pytest.approx(2.0)


def test_rolling_statistics_requires_positive_parameters() -> None:
    with pytest.raises(ValueError):
        RollingStatisticsByKey[str](maxlen=0)

    with pytest.raises(ValueError):
        RollingStatisticsByKey[str](window=0.0)


def test_rolling_mean_alias_matches_average() -> None:
    averages = RollingAverageByKey[str](maxlen=3)
    alias = RollingMeanByKey[str](maxlen=3)

    for timestamp, value in enumerate((2.0, 4.0, 6.0)):
        averages.observe("imu", value, timestamp=float(timestamp))
        alias.observe("imu", value, timestamp=float(timestamp))

    assert averages.get("imu") == alias.get("imu")
    assert averages.snapshot() == alias.snapshot()
