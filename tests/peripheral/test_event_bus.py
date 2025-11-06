import pytest

from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import EventBus


def test_emit_orders_callbacks_by_priority_then_fifo():
    bus = EventBus()
    order: list[str] = []

    bus.subscribe("button", lambda evt: order.append("low"), priority=0)
    bus.subscribe("button", lambda evt: order.append("mid"), priority=5)
    bus.subscribe("button", lambda evt: order.append("mid-2"), priority=5)
    bus.subscribe("button", lambda evt: order.append("high"), priority=10)

    bus.emit("button", data=None)

    assert order == ["high", "mid", "mid-2", "low"]


def test_run_on_event_decorator_registers_handler():
    bus = EventBus()
    captured: list[int] = []

    @bus.run_on_event("tick")
    def _handler(event: Input) -> None:
        captured.append(event.producer_id)

    bus.emit("tick", data="value", producer_id=42)

    assert captured == [42]


def test_subscriber_failures_do_not_block_others(caplog: pytest.LogCaptureFixture):
    bus = EventBus()
    caplog.set_level("ERROR")
    calls: list[str] = []

    def _bad(_: Input) -> None:
        raise RuntimeError("boom")

    bus.subscribe("sensor", _bad)
    bus.subscribe("sensor", lambda event: calls.append(event.event_type))

    bus.emit(Input(event_type="sensor", data={}))

    assert calls == ["sensor"]
    assert any("EventBus subscriber" in message for message in caplog.messages)
