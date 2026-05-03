"""Validate switch threading so blocking readers do not stall peripheral startup or input responsiveness."""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest
from manyfold import Graph

from heart.peripheral.switch import (FakeSwitch, Switch,
                                     switch_detection_route,
                                     switch_state_event_route)
from heart.utilities.reactive import Disposable
from heart.utilities.reactive_threads import \
    reset_reactive_threading_state_for_tests

BUTTON_PRESS_EVENT = "button.press"
BUTTON_LONG_PRESS_EVENT = "button.long_press"
SWITCH_ROTATION_EVENT = "switch.rotation"


@pytest.fixture(autouse=True)
def _reset_reactive_threads() -> Iterator[None]:
    reset_reactive_threading_state_for_tests()
    yield
    reset_reactive_threading_state_for_tests()


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


class _SerialStub:
    def __init__(self, packets: Iterator[bytes]) -> None:
        self._packets = packets

    def __enter__(self) -> "_SerialStub":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    @property
    def in_waiting(self) -> int:
        return 1

    def readline(self) -> bytes:
        try:
            return next(self._packets)
        except StopIteration:
            raise KeyboardInterrupt


class TestSwitchManyfoldRuntime:
    def test_update_due_to_data_tracks_rotation_and_button_edges(self) -> None:
        switch = Switch(port="/dev/null", baudrate=115200)

        switch.update_due_to_data({"event_type": SWITCH_ROTATION_EVENT, "data": 4})
        switch.update_due_to_data({"event_type": BUTTON_PRESS_EVENT, "data": 1})
        switch.update_due_to_data({"event_type": SWITCH_ROTATION_EVENT, "data": 9})
        switch.update_due_to_data({"event_type": BUTTON_LONG_PRESS_EVENT, "data": 1})

        assert switch._snapshot().rotational_value == 9
        assert switch._snapshot().button_value == 1
        assert switch._snapshot().long_button_value == 1
        assert switch._snapshot().rotation_since_last_button_press == 5
        assert switch._snapshot().rotation_since_last_long_button_press == 0

    def test_detection_node_spawns_serial_state_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        detected = Switch(port="/dev/ttyUSB0", baudrate=115200)
        payloads = iter(
            (
                b'{"event_type":"switch.rotation","data":3,"producer_id":0}\n',
                b'{"event_type":"button.press","data":1,"producer_id":0}\n',
            )
        )

        def _detect(cls) -> Iterator[Switch]:
            yield detected

        monkeypatch.setattr(Switch, "detect", classmethod(_detect))
        monkeypatch.setattr(
            detected,
            "_connect_to_ser",
            lambda: _SerialStub(payloads),
        )
        graph = Graph()
        registered: list[Switch] = []

        handle = Switch.detection_node(
            spawn_sources=True,
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)
        assert registered == [detected]
        assert len(handle.spawned_handles) == 1

        spawned = handle.spawned_handles[0]
        spawned.loop_handle.loop.run(spawned.loop_handle.token)

        latest_detection = graph.latest(switch_detection_route())
        latest_state = graph.latest(switch_state_event_route())
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.switch.detected"
        assert latest_state is not None
        assert latest_state.value.event_type == "peripheral.switch.state"
        assert latest_state.value.data["rotational_value"] == 3
        assert latest_state.value.data["button_value"] == 1

    def test_fake_switch_install_node_publishes_state_snapshot(self) -> None:
        switch = FakeSwitch()
        switch._handle_browse(2)
        switch._handle_activate(object())
        graph = Graph()

        handle = switch.install_node(
            graph,
            poll_interval_seconds=0,
            start_immediately=False,
        )
        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_state = graph.latest(switch_state_event_route())
        assert latest_state is not None
        assert latest_state.value.event_type == "peripheral.switch.state"
        assert latest_state.value.data["rotational_value"] == 2
        assert latest_state.value.data["button_value"] == 1
        assert latest_state.value.identity.id == "fake_switch"
