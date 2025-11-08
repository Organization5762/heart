"""Unit tests for :class:`heart.events.metrics.CountByKey`."""


import pytest

from heart.events.metrics import CountByKey


@pytest.fixture()
def counter() -> CountByKey[str]:
    return CountByKey[str]()


def test_count_by_key_increments_per_key(counter: CountByKey[str]) -> None:
    counter.observe("sensor-1")
    counter.observe("sensor-1", amount=2)
    counter.observe("sensor-2")

    assert counter.get("sensor-1") == 3
    assert counter.get("sensor-2") == 1
    assert counter.get("missing") == 0


def test_count_by_key_snapshot_returns_copy(counter: CountByKey[str]) -> None:
    counter.observe("sensor-1")

    snapshot = counter.snapshot()
    counter.observe("sensor-1")

    assert snapshot == {"sensor-1": 1}
    assert counter.snapshot() == {"sensor-1": 2}
    assert snapshot is not counter.snapshot()


def test_count_by_key_reset_clears_all_counts(counter: CountByKey[str]) -> None:
    counter.observe("sensor-1")
    counter.observe("sensor-2", amount=4)

    counter.reset()

    assert counter.snapshot() == {}
    assert counter.get("sensor-1") == 0
    assert counter.get("sensor-2") == 0