from __future__ import annotations

import pytest

from heart.events.metrics import TimeDecayedActivity


class _FakeClock:
    def __init__(self) -> None:
        self.current = 0.0

    def advance(self, delta: float) -> None:
        self.current += delta

    def __call__(self) -> float:
        return self.current


def test_time_decayed_activity_linear_decay() -> None:
    clock = _FakeClock()
    metric = TimeDecayedActivity[str](horizon=10.0, curve="linear", clock=clock)

    metric.observe("merge", value=4.0)
    clock.advance(2.5)

    snapshot = metric.get("merge")
    assert snapshot.decayed_value == pytest.approx(3.0)
    assert snapshot.samples == 1
    assert snapshot.horizon_s == pytest.approx(10.0)
    assert snapshot.decay_curve == "linear"

    clock.advance(10.0)
    snapshot = metric.get("merge")
    assert snapshot.decayed_value == pytest.approx(0.0)
    assert snapshot.samples == 0


def test_time_decayed_activity_quadratic_decay() -> None:
    clock = _FakeClock()
    metric = TimeDecayedActivity[str](horizon=5.0, curve="quadratic", clock=clock)

    metric.observe("merge", value=2.0)
    clock.advance(1.0)
    metric.observe("merge", value=3.0)
    clock.advance(1.0)

    snapshot = metric.get("merge")
    expected = (2.0 * (0.6**2)) + (3.0 * (0.8**2))
    assert snapshot.decayed_value == pytest.approx(expected)
    assert snapshot.samples == 2
    assert snapshot.decay_curve == "quadratic"

    clock.advance(4.0)
    snapshot = metric.get("merge")
    assert snapshot.decayed_value == pytest.approx(0.0)
    assert snapshot.samples == 0


def test_time_decayed_activity_reset_and_validation() -> None:
    metric = TimeDecayedActivity[str](horizon=1.0)
    metric.observe("merge", value=1.0, timestamp=0.0)
    metric.reset("merge")
    snapshot = metric.get("merge")
    assert snapshot.decayed_value == pytest.approx(0.0)

    metric.observe("merge", value=1.0, timestamp=0.0)
    metric.reset()
    snapshot = metric.get("merge")
    assert snapshot.decayed_value == pytest.approx(0.0)


def test_time_decayed_activity_parameter_validation() -> None:
    with pytest.raises(ValueError):
        TimeDecayedActivity[str](horizon=0.0)

    with pytest.raises(ValueError):
        TimeDecayedActivity[str](horizon=1.0, curve="cubic")
