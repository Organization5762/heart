"""Tests for peripheral event streams."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, get_ident
from typing import Any

from manyfold import Graph, StreamNode

from heart.peripheral.core import (Input, Peripheral, PeripheralInfo,
                                   PeripheralLocation,
                                   PeripheralMessageEnvelope, PeripheralTag)
from heart.peripheral.core.streams import (EventStream, GraphRouteStream,
                                           StreamPriority,
                                           _schedule_background,
                                           combine_latest,
                                           observe_on_background,
                                           runtime_route)
from heart.peripheral.core.subscriptions import (CallbackObservable,
                                                 NoopSubscription)


class CountingPeripheral(Peripheral[int]):
    """Capture subscription counts so shared streams avoid duplicate work."""

    def __init__(self, counter: dict[str, int]) -> None:
        self._counter = counter

    def _event_stream(self) -> StreamNode[int]:
        def on_subscribe(observer: Any, scheduler: Any) -> NoopSubscription:
            self._counter["subscriptions"] += 1
            return NoopSubscription()

        return CallbackObservable(on_subscribe)


class EmittingPeripheral(Peripheral[int]):
    """Peripheral backed by a controllable event stream for envelope tests."""

    def __init__(self) -> None:
        self.events: EventStream[int] = EventStream()

    def _event_stream(self) -> StreamNode[int]:
        return self.events


class TestPeripheralObserveSharing:
    """Group tests for shared peripheral streams to avoid duplicate source work."""

    def test_observe_shares_subscription(self) -> None:
        """Ensure observe shares a single subscription so redundant polling is avoided for scalability."""
        counter = {"subscriptions": 0}
        peripheral = CountingPeripheral(counter)
        stream = peripheral.observe

        subscription_a = stream.subscribe()
        subscription_b = stream.subscribe()
        try:
            assert counter["subscriptions"] == 1, (
                "Observe should share the underlying stream."
            )
        finally:
            subscription_a.dispose()
            subscription_b.dispose()

    def test_observe_unwraps_graph_pipeline_envelopes(self) -> None:
        """Ensure peripheral observers receive domain payloads instead of Manyfold route envelopes."""
        peripheral = EmittingPeripheral()
        observed: list[PeripheralMessageEnvelope[int]] = []

        subscription = peripheral.observe.subscribe(observed.append)
        try:
            peripheral.events.emit(7)

            assert observed
            assert observed[-1].data == 7
        finally:
            subscription.dispose()


class TestGraphRouteStreamTransforms:
    def test_route_stream_retains_latest_value_only(self) -> None:
        """Keep per-frame runtime streams from accumulating unbounded graph history."""
        graph = Graph()
        route = runtime_route("test_event_stream_retention", "HeartRetention")
        stream = GraphRouteStream[int](graph, route)

        for value in range(10):
            stream.on_next(value)

        assert stream.value == 9
        assert len(graph._history[route.route_ref.display()]) == 1

    def test_combine_latest_accepts_graph_route_stream_sources(self) -> None:
        graph = Graph()
        route_a = runtime_route("test_event_stream_combine_a", "HeartCombineA")
        route_b = runtime_route("test_event_stream_combine_b", "HeartCombineB")
        stream_a = GraphRouteStream[int](graph, route_a)
        stream_b = GraphRouteStream[int](graph, route_b)
        observed: list[tuple[int, int]] = []

        subscription = combine_latest(stream_a, stream_b).subscribe(observed.append)
        try:
            stream_a.on_next(1)
            stream_b.on_next(2)
            stream_a.on_next(3)

            assert observed == [(1, 2), (3, 2)]
        finally:
            subscription.dispose()

    def test_callback_pipeline_connects_graph_route_to_python_sink(self) -> None:
        graph = Graph()
        route = runtime_route(
            "test_event_stream_callback", "HeartTestEventStreamCallback"
        )
        stream = GraphRouteStream[int](graph, route)
        observed: list[int] = []

        connection = (
            stream.map(lambda value: value + 1, name="increment")
            .filter(lambda value: value > 2, name="greater-than-two")
            .callback(observed.append, name="collect")
        )
        try:
            stream.on_next(1)
            stream.on_next(2)

            assert observed == [3]
        finally:
            connection.remove()

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

        transformed = stream.map(mapper)
        doubled = stream.map(lambda value: value * 2)
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


class TestBackgroundStreamScheduling:
    def test_observe_on_background_delivers_off_caller_thread(self) -> None:
        source: EventStream[int] = EventStream()
        caller_thread = get_ident()
        delivered = Event()
        observed: list[tuple[int, int]] = []

        subscription = observe_on_background(source).subscribe(
            lambda value: (observed.append((value, get_ident())), delivered.set())
        )
        try:
            source.emit(3)

            assert delivered.wait(1.0)
            assert observed == [(3, observed[0][1])]
            assert observed[0][1] != caller_thread
        finally:
            subscription.dispose()

    def test_background_scheduler_prefers_higher_priority_pending_work(self) -> None:
        started = Event()
        release = Event()
        completed = Event()
        observed: list[str] = []

        def blocking_low_priority() -> None:
            started.set()
            assert release.wait(1.0)
            observed.append("low-blocking")

        def record(value: str) -> None:
            observed.append(value)
            if len(observed) == 3:
                completed.set()

        _schedule_background(
            blocking_low_priority,
            priority=StreamPriority.LOW,
        )
        assert started.wait(1.0)

        _schedule_background(lambda: record("low-pending"), priority=StreamPriority.LOW)
        _schedule_background(lambda: record("high-pending"), priority=StreamPriority.HIGH)
        release.set()

        assert completed.wait(1.0)
        assert observed == ["low-blocking", "high-pending", "low-pending"]


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
