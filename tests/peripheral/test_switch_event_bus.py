from __future__ import annotations

from typing import Any

import pytest

from heart.firmware_io.constants import BUTTON_PRESS, SWITCH_ROTATION
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.switch import BluetoothSwitch, FakeSwitch


def test_fake_switch_emits_bus_events() -> None:
    bus = EventBus()
    captured: list[tuple[str, Any, int]] = []
    lifecycle: list[str] = []

    bus.subscribe(
        BUTTON_PRESS,
        lambda event: captured.append((event.event_type, event.data, event.producer_id)),
    )
    bus.subscribe(
        FakeSwitch.EVENT_LIFECYCLE,
        lambda event: lifecycle.append(event.data["status"]),
    )

    switch = FakeSwitch()
    switch.attach_event_bus(bus)
    switch.update_due_to_data({"event_type": BUTTON_PRESS, "data": 1, "producer_id": 7})

    assert lifecycle and lifecycle[0] == "connected"

    assert captured == [(BUTTON_PRESS, 1, 7)]
    assert switch.get_button_value() == 1

    entry = bus.state_store.get_latest(BUTTON_PRESS, producer_id=7)
    assert entry is not None
    assert entry.data == 1


class _DummyListener:
    def __init__(self, device) -> None:  # pragma: no cover - invoked indirectly
        self.device = device

    def start(self) -> None:  # pragma: no cover - network operations skipped
        return None

    def consume_events(self):  # pragma: no cover - generator interface
        return []

    def close(self) -> None:  # pragma: no cover - nothing to do
        return None

    @staticmethod
    def _discover_devices():  # pragma: no cover - unused in tests
        return []


def test_bluetooth_switch_routes_producer_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("heart.peripheral.switch.UartListener", _DummyListener)

    bus = EventBus()
    captured: list[tuple[str, int, int]] = []

    bus.subscribe(
        BUTTON_PRESS,
        lambda event: captured.append((event.event_type, event.data, event.producer_id)),
    )
    bus.subscribe(
        SWITCH_ROTATION,
        lambda event: captured.append((event.event_type, event.data, event.producer_id)),
    )

    switch = BluetoothSwitch(device=object())
    switch.attach_event_bus(bus)

    switch.update_due_to_data({"event_type": BUTTON_PRESS, "data": 1, "producer_id": 2})
    switch.update_due_to_data({"event_type": SWITCH_ROTATION, "data": 5, "producer_id": 0})

    assert (BUTTON_PRESS, 1, 2) in captured
    assert (SWITCH_ROTATION, 5, 0) in captured

    rotation_entry = bus.state_store.get_latest(SWITCH_ROTATION, producer_id=0)
    assert rotation_entry is not None
    assert rotation_entry.data == 5
    assert switch.get_rotational_value() == 5
