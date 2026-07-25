"""Tests for peripheral event streams."""

from __future__ import annotations

from datetime import datetime, timezone

from manyfold import Graph, Subscribable
from manyfold.architecture import NewValues

from heart.peripheral.core import (Input, Peripheral, PeripheralInfo,
                                   PeripheralLocation,
                                   PeripheralMessageEnvelope, PeripheralTag)
from heart.peripheral.core.streams import GraphRouteStream, runtime_route


class EmittingPeripheral(Peripheral[int]):
    """Peripheral backed by a controllable event stream for envelope tests."""

    def __init__(self) -> None:
        self.events = NewValues[int](name="test.emitting_peripheral.events")

    def _event_stream(self) -> Subscribable[int]:
        return self.events


class TestPeripheralObserve:
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

        snapshot = next(graph.retention_snapshot(route))

        assert stream.value == 9
        assert snapshot.replay_count == 1
        assert snapshot.payload_count == 1

    def test_route_stream_uses_manyfold_nowait_publish_when_available(self) -> None:
        graph = Graph()
        route = runtime_route("test_event_stream_nowait", "HeartNowait")
        stream = GraphRouteStream[int](graph, route)
        publish_nowait = graph.publish_nowait
        calls: list[tuple[object, int]] = []

        def record_publish_nowait(target: object, value: int) -> None:
            calls.append((target, value))
            publish_nowait(target, value)

        def unexpected_publish(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(
                "GraphRouteStream.emit should not fall back to publish"
            )

        graph.publish_nowait = record_publish_nowait  # type: ignore[method-assign]
        graph.publish = unexpected_publish  # type: ignore[method-assign]

        stream.on_next(7)

        assert calls == [(route, 7)]
        assert stream.value == 7


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
