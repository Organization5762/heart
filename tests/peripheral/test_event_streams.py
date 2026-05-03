"""Tests for peripheral reactive event streams."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from manyfold import Graph

import heart.utilities.reactive as reactive
from heart.peripheral.core import (Input, Peripheral, PeripheralInfo,
                                   PeripheralLocation,
                                   PeripheralMessageEnvelope, PeripheralTag)
from heart.peripheral.core.streams import GraphRouteStream, runtime_route
from heart.utilities.reactive import Disposable


class CountingPeripheral(Peripheral[int]):
    """Capture subscription counts so shared streams avoid duplicate work."""

    def __init__(self, counter: dict[str, int]) -> None:
        self._counter = counter

    def _event_stream(self) -> reactive.Observable[int]:
        def on_subscribe(observer: Any, scheduler: Any) -> Disposable:
            self._counter["subscriptions"] += 1
            return Disposable()

        return reactive.create(on_subscribe)


class TestPeripheralObserveSharing:
    """Group tests for shared peripheral streams to keep reactive fan-out efficient."""

    def test_observe_shares_subscription(self) -> None:
        """Ensure observe shares a single subscription so redundant polling is avoided for scalability."""
        counter = {"subscriptions": 0}
        peripheral = CountingPeripheral(counter)
        stream = peripheral.observe

        subscription_a = stream.subscribe()
        subscription_b = stream.subscribe()
        try:
            assert counter["subscriptions"] == 1, "Observe should share the underlying stream."
        finally:
            subscription_a.dispose()
            subscription_b.dispose()


class TestGraphRouteStreamTransforms:
    def test_pipe_delegates_operator_sharing_to_observable_pipeline(
        self,
    ) -> None:
        graph = Graph()
        route = runtime_route("test_event_stream_map", "HeartTestEventStreamMap")
        stream = GraphRouteStream[int](graph, route)
        calls = {"mapper": 0}

        def mapper(value: int) -> int:
            calls["mapper"] += 1
            return value + 1

        transformed = stream.pipe(
            reactive.operators.map(mapper),
            reactive.operators.share(),
        )
        doubled = stream.pipe(reactive.operators.map(lambda value: value * 2))
        observed_a: list[int] = []
        observed_b: list[int] = []
        observed_doubled: list[int] = []

        subscription_a = transformed.subscribe(observed_a.append)
        subscription_b = transformed.subscribe(observed_b.append)
        subscription_doubled = doubled.subscribe(observed_doubled.append)
        try:
            stream.on_next(41)

            assert observed_a == [42]
            assert observed_b == [42]
            assert observed_doubled == [82]
            assert calls["mapper"] == 1
        finally:
            subscription_a.dispose()
            subscription_b.dispose()
            subscription_doubled.dispose()


class TestManyfoldSensorEnvelopeBridge:
    """Validate Heart peripheral envelopes can cross the Manyfold sensor boundary."""

    def test_peripheral_info_converts_to_sensor_identity(self) -> None:
        observed_at = datetime(2026, 5, 2, tzinfo=timezone.utc)
        info = PeripheralInfo(
            id="switch:main",
            tags=[PeripheralTag(name="input_variant", variant="button")],
            location=PeripheralLocation(x=1.0, y=2.0, z=3.0, time=observed_at),
        )

        identity = info.to_sensor_identity()

        assert identity.id == "switch:main"
        assert identity.tags[0].name == "input_variant"
        assert identity.tags[0].variant == "button"
        assert identity.location.x == 1.0
        assert identity.location.timestamp == observed_at.timestamp()

    def test_input_and_envelope_convert_to_sensor_events(self) -> None:
        observed_at = datetime(2026, 5, 2, tzinfo=timezone.utc)
        input_event = Input(
            event_type="peripheral.radio.command.raw",
            data={"command": "S"},
            timestamp=observed_at,
        )
        envelope = PeripheralMessageEnvelope(
            peripheral_info=PeripheralInfo(id="radio:bridge"),
            data={"payload": [1, 2, 3]},
        )

        command_event = input_event.to_sensor_event(sequence_number=7)
        packet_event = envelope.to_sensor_event(
            event_type="peripheral.radio.packet",
            observed_at=observed_at,
            sequence_number=8,
        )

        assert command_event.event_type == "peripheral.radio.command.raw"
        assert command_event.sequence_number == 7
        assert command_event.observed_at == observed_at.timestamp()
        assert packet_event.identity.id == "radio:bridge"
        assert packet_event.data == {"payload": [1, 2, 3]}
