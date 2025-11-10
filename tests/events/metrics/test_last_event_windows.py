"""Tests for high-level event window helpers."""

from __future__ import annotations

from heart.events.metrics import (LastEventsWithinTimeWindow, LastNEvents,
                                  LastNEventsWithinTimeWindow)


class TestEventsMetricsLastEventWindows:
    """Group Events Metrics Last Event Windows tests so events metrics last event windows behaviour stays reliable. This preserves confidence in events metrics last event windows for end-to-end scenarios."""

    def test_last_n_events_retains_recent_entries(self) -> None:
        """Verify that LastNEvents keeps only the most recent events up to the configured count. This ensures bounded memory usage while surfacing the freshest samples."""
        window = LastNEvents[str](count=3)

        for index in range(5):
            window.append(f"event-{index}", timestamp=float(index))

        assert window.values() == ("event-2", "event-3", "event-4")



    def test_last_events_within_time_window_filters_by_age(self) -> None:
        """Verify that LastEventsWithinTimeWindow filters out events older than the allowed window. This keeps time-based dashboards aligned with current system behaviour."""
        window = LastEventsWithinTimeWindow[str](window=2.0)

        window.append("event-0", timestamp=0.0)
        window.append("event-1", timestamp=1.0)
        window.append("event-2", timestamp=3.1)

        assert window.values() == ("event-2",)



    def test_last_n_events_within_time_window_enforces_both_limits(self) -> None:
        """Verify that LastNEventsWithinTimeWindow prunes by both age and count limits. This demonstrates hybrid retention for scenarios needing both freshness and bounded storage."""
        window = LastNEventsWithinTimeWindow[str](count=2, window=3.0)

        window.append("event-0", timestamp=0.0)
        window.append("event-1", timestamp=1.0)
        window.append("event-2", timestamp=2.0)
        window.append("event-3", timestamp=6.0)

        assert window.values() == ("event-3",)



    def test_last_n_events_within_time_window_limits_count(self) -> None:
        """Verify that LastNEventsWithinTimeWindow trims to the latest N events when all are timely. This confirms consistent behaviour when data arrives within SLA windows."""
        window = LastNEventsWithinTimeWindow[str](count=2, window=5.0)

        for index in range(4):
            window.append(f"event-{index}", timestamp=float(index))

        assert window.values() == ("event-2", "event-3")
