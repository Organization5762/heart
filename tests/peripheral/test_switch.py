"""Validate switch threading so blocking readers do not stall peripheral startup or input responsiveness."""

from __future__ import annotations

import threading

import pytest
from reactivex.disposable import Disposable

from heart.peripheral.switch import Switch
from heart.utilities.reactivex_threads import \
    reset_reactivex_threading_state_for_tests


@pytest.fixture(autouse=True)
def _reset_reactivex_threads() -> None:
    reset_reactivex_threading_state_for_tests()
    yield
    reset_reactivex_threading_state_for_tests()


class TestSwitchRunLoopIsolation:
    """Group switch run-loop tests so blocking serial readers stay off the startup path and remain observable."""

    def test_run_returns_while_reader_waits_on_blocking_scheduler(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify the serial reader subscribes on the blocking scheduler so peripheral startup is not pinned behind a long-lived read loop."""
        switch = Switch(port="/dev/null", baudrate=115200)
        started = threading.Event()
        release = threading.Event()
        observed: list[dict[str, object]] = []

        def _read_from_switch(_observer, _scheduler=None) -> Disposable:
            started.set()
            release.wait(timeout=1.0)
            return Disposable()

        monkeypatch.setattr(switch, "_read_from_switch", _read_from_switch)
        monkeypatch.setattr(switch, "update_due_to_data", observed.append)

        switch.run()

        assert started.wait(timeout=0.5)
        assert observed == []
        assert switch._subscription is not None

        release.set()
