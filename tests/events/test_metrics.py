"""Unit tests for sensor metric aggregations."""

from __future__ import annotations

import math

import pytest

from heart.events.metrics import (CountByKey, EventWindow,
                                  LastEventsWithinTimeWindow, LastNEvents,
                                  LastNEventsWithinTimeWindow,
                                  RollingAverageByKey, RollingStatisticsByKey,
                                  RollingStddevByKey, combine_windows)


def test_count_by_key() -> None:
    counter = CountByKey[str]()
    counter.observe("sensor-1")
    counter.observe("sensor-1", amount=2)
    counter.observe("sensor-2")

    assert counter.get("sensor-1") == 3
    assert counter.get("sensor-2") == 1
    assert counter.get("missing") == 0


def test_rolling_statistics_by_key_maxlen() -> None:
    stats = RollingStatisticsByKey[str](maxlen=3)

    stats.observe("imu", 1.0, timestamp=0.0)
    stats.observe("imu", 2.0, timestamp=1.0)
    stats.observe("imu", 3.0, timestamp=2.0)
    stats.observe("imu", 4.0, timestamp=3.0)

    snapshot = stats.snapshot()["imu"]
    assert snapshot.count == 3
    assert snapshot.mean == pytest.approx(3.0)
    assert snapshot.stddev == pytest.approx(math.sqrt(2 / 3))


def test_rolling_statistics_by_key_time_window() -> None:
    stats = RollingStatisticsByKey[str](window=5.0)

    stats.observe("imu", 1.0, timestamp=0.0)
    stats.observe("imu", 3.0, timestamp=1.0)
    stats.observe("imu", 5.0, timestamp=6.0)

    snapshot = stats.snapshot()["imu"]
    assert snapshot.count == 2
    assert snapshot.mean == pytest.approx(4.0)
    assert snapshot.stddev == pytest.approx(1.0)


def test_rolling_average_and_stddev_by_key() -> None:
    averages = RollingAverageByKey[str](maxlen=2)
    stddevs = RollingStddevByKey[str](maxlen=2)

    averages.observe("imu", 5.0, timestamp=0.0)
    stddevs.observe("imu", 5.0, timestamp=0.0)
    averages.observe("imu", 9.0, timestamp=1.0)
    stddevs.observe("imu", 9.0, timestamp=1.0)

    assert averages.get("imu") == pytest.approx(7.0)
    assert stddevs.get("imu") == pytest.approx(2.0)


def test_last_n_events() -> None:
    window = LastNEvents[str](count=3)

    for index in range(5):
        window.append(f"event-{index}", timestamp=float(index))

    assert window.values() == ("event-2", "event-3", "event-4")


def test_last_events_within_time_window() -> None:
    window = LastEventsWithinTimeWindow[str](window=2.0)

    window.append("event-0", timestamp=0.0)
    window.append("event-1", timestamp=1.0)
    window.append("event-2", timestamp=4.0)

    assert window.values() == ("event-2",)


def test_last_n_events_within_time_window() -> None:
    window = LastNEventsWithinTimeWindow[str](count=2, window=3.0)

    window.append("event-0", timestamp=0.0)
    window.append("event-1", timestamp=1.0)
    window.append("event-2", timestamp=2.0)
    window.append("event-3", timestamp=6.0)

    assert window.values() == ("event-3",)


def test_composed_window_matches_helper() -> None:
    last_n = LastNEvents[str](count=2)
    within_window = LastEventsWithinTimeWindow[str](window=3.0)

    composed = combine_windows(last_n, within_window)
    helper = LastNEventsWithinTimeWindow[str](count=2, window=3.0)

    for timestamp, event in enumerate(("a", "b", "c", "d")):
        composed.append(event, timestamp=float(timestamp))
        helper.append(event, timestamp=float(timestamp))

    assert composed.values() == helper.values()


def test_event_window_extend() -> None:
    window: EventWindow[int] = LastNEvents(count=4)
    window.extend([1, 2, 3, 4], timestamp=0.0, step=0.5)

    assert window.values() == (1, 2, 3, 4)
