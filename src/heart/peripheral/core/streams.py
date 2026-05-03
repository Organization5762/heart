from __future__ import annotations

from functools import cached_property
from typing import Any, Callable, Generic, Iterable, TypeVar

from manyfold import (Graph, Layer, OwnerName, Plane, Schema, StreamFamily,
                      StreamName, TypedRoute, Variant, route)

from heart.peripheral.core import Peripheral, PeripheralMessageEnvelope
from heart.peripheral.switch import BaseSwitch, FakeSwitch, SwitchState
from heart.utilities import reactive
from heart.utilities.reactive_threads import pipe_in_background

PeripheralSource = Callable[[], Iterable[Peripheral[Any]]]
RUNTIME_OWNER = OwnerName("heart.runtime")
RUNTIME_FAMILY = StreamFamily("runtime")
T = TypeVar("T")


def runtime_route(name: str, schema_id: str) -> Any:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=RUNTIME_OWNER,
        family=RUNTIME_FAMILY,
        stream=StreamName(name),
        variant=Variant.State,
        schema=Schema.any(schema_id),
    )


class GraphRouteStream(Generic[T]):
    """Observable-like route handle backed by a Manyfold graph."""

    def __init__(self, graph: Graph, route_ref: TypedRoute[T]) -> None:
        self._graph = graph
        self._route = route_ref

    @property
    def value(self) -> T | None:
        latest = self._graph.latest(self._route)
        return None if latest is None else latest.value

    def on_next(self, value: T) -> None:
        self._graph.publish(self._route, value)

    def subscribe(self, *args: Any, **kwargs: Any) -> Any:
        return self._observable().subscribe(*args, **kwargs)

    def pipe(self, *operators: Any) -> reactive.Observable[Any]:
        return self._observable().pipe(*operators)

    def _observable(self) -> reactive.Observable[T]:
        return self._graph.observe(self._route).pipe(
            reactive.operators.map(lambda envelope: envelope.value)
        )


class PeripheralStreams:
    """Build shared reactive streams for detected peripherals."""

    def __init__(self, graph: Graph, peripheral_source: PeripheralSource) -> None:
        self._graph = graph
        self._peripheral_source = peripheral_source

    def main_switch_subscription(self) -> reactive.Observable[SwitchState]:
        return self._switch_subscription(include_fake_switches=True)

    def physical_main_switch_subscription(
        self,
    ) -> reactive.Observable[SwitchState]:
        return self._switch_subscription(include_fake_switches=False)

    def _switch_subscription(
        self,
        *,
        include_fake_switches: bool,
    ) -> reactive.Observable[SwitchState]:
        main_switches = [
            peripheral
            for peripheral in self._peripheral_source()
            if isinstance(peripheral, BaseSwitch)
            and (include_fake_switches or not isinstance(peripheral, FakeSwitch))
        ]
        observables = [peripheral.observe for peripheral in main_switches]

        if not observables:
            return reactive.empty()

        merged = pipe_in_background(
            reactive.merge(*observables),
            reactive.operators.map(PeripheralMessageEnvelope[SwitchState].unwrap_peripheral)
        )
        return merged

    @cached_property
    def game_tick(self) -> GraphRouteStream[Any]:
        return GraphRouteStream(
            self._graph,
            runtime_route("game_tick", "HeartRuntimeGameTick"),
        )

    @cached_property
    def window(self) -> GraphRouteStream[Any]:
        return GraphRouteStream(
            self._graph,
            runtime_route("window", "HeartRuntimeWindow"),
        )

    @cached_property
    def clock(self) -> GraphRouteStream[Any]:
        return GraphRouteStream(
            self._graph,
            runtime_route("clock", "HeartRuntimeClock"),
        )
