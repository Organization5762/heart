"""Unit tests for :class:`heart.events.metrics.CountByKey`."""

from __future__ import annotations

import pytest

from heart.events.metrics import CountByKey


@pytest.fixture()
def counter() -> CountByKey[str]:
    return CountByKey[str]()


class TestEventsMetricsCountByKey:
    """Group Events Metrics Count By Key tests so events metrics count by key behaviour stays reliable. This preserves confidence in events metrics count by key for end-to-end scenarios."""

    def test_count_by_key_increments_per_key(self, counter: CountByKey[str]) -> None:
        """Verify that CountByKey accumulates counts independently for each key. This ensures multi-device metrics stay isolated so one sensor cannot skew another's totals."""
        counter.observe("sensor-1")
        counter.observe("sensor-1", amount=2)
        counter.observe("sensor-2")

        assert counter.get("sensor-1") == 3
        assert counter.get("sensor-2") == 1
        assert counter.get("missing") == 0



    def test_count_by_key_snapshot_returns_copy(self, counter: CountByKey[str]) -> None:
        """Verify that snapshot returns a detached copy unaffected by later updates. This prevents monitoring dashboards from mutating shared state when rendering statistics."""
        counter.observe("sensor-1")

        snapshot = counter.snapshot()
        counter.observe("sensor-1")

        assert snapshot == {"sensor-1": 1}
        assert counter.snapshot() == {"sensor-1": 2}
        assert snapshot is not counter.snapshot()



    def test_count_by_key_reset_clears_all_counts(self, counter: CountByKey[str]) -> None:
        """Verify that reset clears every tracked count and zeros subsequent lookups. This supports periodic reporting cycles where counters must start fresh."""
        counter.observe("sensor-1")
        counter.observe("sensor-2", amount=4)

        counter.reset()

        assert counter.snapshot() == {}
        assert counter.get("sensor-1") == 0
        assert counter.get("sensor-2") == 0
