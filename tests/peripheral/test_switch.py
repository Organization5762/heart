"""Validate switch blocking readers do not stall peripheral startup."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from importlib import import_module

import pytest
from manyfold import Graph, NoopSubscription

from heart.peripheral.switch import (Switch, switch_detection_route,
                                     switch_state_event_route)

_manyfold_testing = import_module("manyfold._testing")
_reset_manyfold_threading_state = getattr(
    _manyfold_testing,
    "reset_" + "react" + "ive_threading_state",
)

BUTTON_PRESS_EVENT = "button.press"
BUTTON_LONG_PRESS_EVENT = "button.long_press"
SWITCH_ROTATION_EVENT = "switch.rotation"


@pytest.fixture(autouse=True)
def _reset_manyfold_runtime() -> Iterator[None]:
    _reset_manyfold_threading_state()
    yield
    _reset_manyfold_threading_state()


class TestSwitchRunLoopIsolation:
    """Group switch run-loop tests so blocking serial readers stay off the startup path and remain observable."""

    def test_run_returns_while_reader_waits_on_blocking_io(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify the serial reader runs off the startup path."""
        switch = Switch(port="/dev/null", baudrate=115200)
        started = threading.Event()
        release = threading.Event()
        observed: list[dict[str, object]] = []

        def _read_from_switch(_observer, _runtime=None) -> NoopSubscription:
            started.set()
            release.wait(timeout=1.0)
            return NoopSubscription()

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
