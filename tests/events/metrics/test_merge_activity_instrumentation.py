from __future__ import annotations

import enum

import pytest

from heart.events.merge_activity import (SupportsMergeSurfaces,
                                         track_merge_activity)
from heart.events.metrics import TimeDecayedActivity


class FakeVariant(enum.Enum):
    ITERATIVE = "iterative"
    BINARY = "binary"


class DummyLoop:
    def __init__(self) -> None:
        self.renderer_variant: FakeVariant = FakeVariant.ITERATIVE
        self.calls: int = 0

    def merge_surfaces(self, surface1: object, surface2: object) -> object:  # pragma: no cover - replaced at runtime
        self.calls += 1
        return surface1


def test_track_merge_activity_records_metric() -> None:
    loop = DummyLoop()
    metric = TimeDecayedActivity[str](horizon=5.0, curve="linear")

    with track_merge_activity(loop, metric):
        result = loop.merge_surfaces("base", "overlay")

    assert result == "base"
    snapshot = metric.snapshot()
    assert pytest.approx(snapshot["merge.activity"].decayed_value, rel=1e-5) == 1.0
    variant_key = "merge.activity.variant.iterative"
    assert pytest.approx(snapshot[variant_key].decayed_value, rel=1e-5) == 1.0


def test_track_merge_activity_restores_method() -> None:
    loop = DummyLoop()
    metric = TimeDecayedActivity[str](horizon=2.0)

    original = loop.merge_surfaces
    with track_merge_activity(loop, metric):
        assert loop.merge_surfaces is not original
    assert loop.merge_surfaces is original


def test_track_merge_activity_accepts_custom_labeler() -> None:
    loop = DummyLoop()
    metric = TimeDecayedActivity[str](horizon=3.0)

    def labeler(_: SupportsMergeSurfaces) -> list[tuple[str, float]]:
        return [("custom.key", 0.5), ("other.key", 2.0)]

    with track_merge_activity(loop, metric, labeler=labeler):
        loop.merge_surfaces("base", "overlay")

    snap = metric.snapshot()
    assert snap["custom.key"].decayed_value == pytest.approx(0.5)
    assert snap["other.key"].decayed_value == pytest.approx(2.0)
