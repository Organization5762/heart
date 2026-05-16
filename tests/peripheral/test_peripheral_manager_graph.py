from __future__ import annotations

from typing import Any, cast

from manyfold import (DetectionNode, Layer, OwnerName, Plane, StreamFamily,
                      StreamName, TypedRoute, Variant, route)
from manyfold.sensor_io import (ManagedGraphNode, SensorEvent, StopToken,
                                sensor_event_schema)

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.core import Peripheral
from heart.peripheral.core.manager import PeripheralManager


def _sensor_event(event_type: str) -> SensorEvent:
    return SensorEvent(event_type=event_type, data={}, observed_at=0.0)


def _event_route(name: str) -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=OwnerName("heart.test"),
        family=StreamFamily("peripheral"),
        stream=StreamName(name),
        variant=Variant.Meta,
        schema=sensor_event_schema(f"HeartTest{name}"),
    )


class _LoaderStub:
    registry: object = object()

    def __init__(self, configuration: PeripheralConfiguration) -> None:
        self._configuration = configuration

    def load(self) -> PeripheralConfiguration:
        return self._configuration


class _DetectedPeripheral(Peripheral[str]):
    def run(self) -> None:
        return None


class TestPeripheralManagerGraph:
    def test_detect_installs_detection_nodes_that_register_peripherals(self) -> None:
        detected = _DetectedPeripheral()
        detection_route = _event_route("detected")
        seen: list[SensorEvent] = []

        def graph_node(*, start_immediately: bool, on_detect: Any | None) -> Any:
            return DetectionNode(
                name="test-detection",
                detector=lambda: (item for item in (detected,)),
                output_route=detection_route,
                mapper=lambda _item: _sensor_event("test.detected"),
                on_detect=on_detect,
                start_immediately=start_immediately,
            )

        manager = PeripheralManager(
            configuration_loader=cast(
                Any,
                _LoaderStub(
                    PeripheralConfiguration(detectors=(), graph_nodes=(graph_node,))
                ),
            )
        )
        manager.graph.observe(detection_route).callback(seen.append)

        manager.detect()

        assert manager.peripherals == (detected,)
        assert len(manager.graph_node_handles) == 1
        assert [event.event_type for event in seen] == ["test.detected"]

    def test_detection_nodes_can_spawn_downstream_sources(self) -> None:
        detected = _DetectedPeripheral()
        detection_route = _event_route("detected")
        source_route = _event_route("source")
        source_events: list[SensorEvent] = []

        def graph_node(*, start_immediately: bool, on_detect: Any | None) -> Any:
            def spawn(_item: object, access: Any) -> None:
                def body(stop: StopToken, graph: Any) -> None:
                    graph.publish(source_route, _sensor_event("test.source"))
                    stop.set()

                access.own(
                    ManagedGraphNode(
                        name="test-source",
                        body=body,
                        output_routes=(source_route,),
                    ).install(access.graph)
                )

            return DetectionNode(
                name="test-detection",
                detector=lambda: (item for item in (detected,)),
                output_route=detection_route,
                mapper=lambda _item: _sensor_event("test.detected"),
                on_detect=on_detect,
                spawn=spawn,
                start_immediately=start_immediately,
            )

        manager = PeripheralManager(
            configuration_loader=cast(
                Any,
                _LoaderStub(
                    PeripheralConfiguration(detectors=(), graph_nodes=(graph_node,))
                ),
            )
        )
        manager.graph.observe(source_route).callback(source_events.append)

        manager.detect()

        assert manager.peripherals == (detected,)
        assert [event.event_type for event in source_events] == ["test.source"]
