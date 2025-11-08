"""Tests for high-level event window helpers."""


from heart.events.metrics import (LastEventsWithinTimeWindow, LastNEvents,
                                  LastNEventsWithinTimeWindow)


def test_last_n_events_retains_recent_entries() -> None:
    window = LastNEvents[str](count=3)

    for index in range(5):
        window.append(f"event-{index}", timestamp=float(index))

    assert window.values() == ("event-2", "event-3", "event-4")


def test_last_events_within_time_window_filters_by_age() -> None:
    window = LastEventsWithinTimeWindow[str](window=2.0)

    window.append("event-0", timestamp=0.0)
    window.append("event-1", timestamp=1.0)
    window.append("event-2", timestamp=3.1)

    assert window.values() == ("event-1", "event-2")


def test_last_n_events_within_time_window_enforces_both_limits() -> None:
    window = LastNEventsWithinTimeWindow[str](count=2, window=3.0)

    window.append("event-0", timestamp=0.0)
    window.append("event-1", timestamp=1.0)
    window.append("event-2", timestamp=2.0)
    window.append("event-3", timestamp=6.0)

    assert window.values() == ("event-3",)


def test_last_n_events_within_time_window_limits_count() -> None:
    window = LastNEventsWithinTimeWindow[str](count=2, window=5.0)

    for index in range(4):
        window.append(f"event-{index}", timestamp=float(index))

    assert window.values() == ("event-2", "event-3")