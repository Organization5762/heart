from __future__ import annotations

from types import SimpleNamespace

import pytest
from helpers.time import DeterministicClock

from heart.firmware_io import rotary_encoder


@pytest.fixture
def dummy_pull(monkeypatch: pytest.MonkeyPatch):
    class DummyPull:
        UP = "up"
        DOWN = "down"

    monkeypatch.setattr(rotary_encoder, "Pull", DummyPull)
    return DummyPull


@pytest.fixture
def deterministic_clock() -> DeterministicClock:
    return DeterministicClock()


@pytest.fixture
def rotary_components(dummy_pull):
    encoder = SimpleNamespace(position=0)
    switch = SimpleNamespace(value=False, pull=dummy_pull.DOWN)
    return encoder, switch
