from __future__ import annotations

from functools import cached_property
from typing import Any, Callable, Generic, Iterable, TypeVar, cast

from manyfold import (CallbackObservable, Graph, Layer, MergeNode, OwnerName,
                      Plane, RoutePipeline, Schema, StreamFamily, StreamName,
                      StreamNode, TypedRoute, Variant, route, stream_from)

from heart.peripheral.core import Peripheral, PeripheralMessageEnvelope
from heart.peripheral.core.nodes import empty_node
from heart.peripheral.switch import BaseSwitch, FakeSwitch, SwitchState

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
    """Route handle backed by a Manyfold graph pipeline."""

    def __init__(self, graph: Graph, route_ref: TypedRoute[T]) -> None:
        self._graph = graph
        self._route = route_ref

    @property
    def value(self) -> T | None:
        latest = self._graph.latest(self._route)
        return None if latest is None else latest.value

    def emit(self, value: T) -> None:
        self._graph.publish(self._route, value)

    def on_next(self, value: T) -> None:
        self.emit(value)

    def subscribe(self, *args: Any, **kwargs: Any) -> Any:
        return self._observable().subscribe(*args, **kwargs)

    def pipe(self, *operators: Any) -> StreamNode[Any]:
        return self._observable().pipe(*operators)

    def share(self) -> StreamNode[T]:
        return self._observable().share()

    def callback(
        self,
        receive: Callable[[T], None],
        *,
        name: str | None = None,
        replay_latest: bool = True,
    ) -> Any:
        return self._graph.observe(self._route, replay_latest=replay_latest).callback(
            receive, name=name
        )

    def map(self, transform: Callable[[T], Any], *, name: str | None = None) -> Any:
        return GraphRoutePipeline(self._graph.observe(self._route).map(transform, name=name))

    def filter(self, predicate: Callable[[T], bool], *, name: str | None = None) -> Any:
        return GraphRoutePipeline(
            self._graph.observe(self._route).filter(predicate, name=name)
        )

    def do_action(
        self,
        on_next: Callable[[T], None] | None = None,
        *_args: Any,
        **_kwargs: Any,
    ) -> StreamNode[T]:
        return cast(
            StreamNode[T],
            stream_from(self, unwrap_envelopes=True).do_action(on_next),
        )

    def scan(self, accumulator: Callable[[Any, T], Any], *, seed: Any = None) -> Any:
        return stream_from(self, unwrap_envelopes=True).scan(accumulator, seed=seed)

    def start_with(self, value: Any) -> Any:
        return stream_from(self, unwrap_envelopes=True).start_with(value)

    def distinct_until_changed(self) -> StreamNode[T]:
        return cast(
            StreamNode[T],
            stream_from(self, unwrap_envelopes=True).distinct_until_changed(),
        )

    def pairwise(self) -> Any:
        return stream_from(self, unwrap_envelopes=True).pairwise()

    def take(self, count: int) -> StreamNode[T]:
        return cast(StreamNode[T], stream_from(self, unwrap_envelopes=True).take(count))

    def with_latest_from(self, *sources: Any) -> Any:
        return stream_from(self, unwrap_envelopes=True).with_latest_from(*sources)

    def flat_map(self, project: Callable[[T], Any]) -> Any:
        return stream_from(self, unwrap_envelopes=True).flat_map(project)

    def switch_latest(self) -> Any:
        return stream_from(self, unwrap_envelopes=True).switch_latest()

    def _observable(self) -> StreamNode[T]:
        def subscribe(observer: Any, scheduler: Any = None) -> Any:
            del scheduler
            return self.callback(observer.on_next, replay_latest=True)

        return cast(StreamNode[T], CallbackObservable(subscribe))


class GraphRoutePipeline(Generic[T]):
    """Value-facing wrapper around a Manyfold route pipeline."""

    def __init__(self, pipeline: RoutePipeline[T]) -> None:
        self._pipeline = pipeline
        self._values = stream_from(pipeline, unwrap_envelopes=True).share()

    def subscribe(self, *args: Any, **kwargs: Any) -> Any:
        return self._values.subscribe(*args, **kwargs)

    def callback(
        self,
        receive: Callable[[T], None],
        *,
        name: str | None = None,
    ) -> Any:
        return self._pipeline.callback(receive, name=name)

    def pipe(self, *operators: Any) -> StreamNode[Any]:
        return self._values.pipe(*operators)

    def share(self) -> StreamNode[T]:
        return cast(StreamNode[T], self._values.share())

    def map(self, transform: Callable[[T], Any], *, name: str | None = None) -> Any:
        return GraphRoutePipeline(self._pipeline.map(transform, name=name))

    def filter(self, predicate: Callable[[T], bool], *, name: str | None = None) -> Any:
        return GraphRoutePipeline(self._pipeline.filter(predicate, name=name))

    def do_action(
        self,
        on_next: Callable[[T], None] | None = None,
        *_args: Any,
        **_kwargs: Any,
    ) -> StreamNode[T]:
        return cast(StreamNode[T], self._values.do_action(on_next).share())

    def scan(self, accumulator: Callable[[Any, T], Any], *, seed: Any = None) -> Any:
        return self._values.scan(accumulator, seed=seed).share()

    def start_with(self, value: Any) -> Any:
        return self._values.start_with(value).share()

    def distinct_until_changed(self) -> StreamNode[T]:
        return cast(StreamNode[T], self._values.distinct_until_changed().share())

    def pairwise(self) -> Any:
        return self._values.pairwise().share()

    def take(self, count: int) -> StreamNode[T]:
        return cast(StreamNode[T], self._values.take(count).share())

    def with_latest_from(self, *sources: Any) -> Any:
        return self._values.with_latest_from(*sources).share()

    def flat_map(self, project: Callable[[T], Any]) -> Any:
        return self._values.flat_map(project).share()

    def switch_latest(self) -> Any:
        return self._values.switch_latest().share()


class PeripheralStreams:
    """Build event streams for detected peripherals."""

    def __init__(self, graph: Graph, peripheral_source: PeripheralSource) -> None:
        self._graph = graph
        self._peripheral_source = peripheral_source

    def main_switch_subscription(self) -> StreamNode[SwitchState]:
        return self._switch_subscription(include_fake_switches=True)

    def physical_main_switch_subscription(self) -> StreamNode[SwitchState]:
        return self._switch_subscription(include_fake_switches=False)

    def _switch_subscription(
        self, *, include_fake_switches: bool
    ) -> StreamNode[SwitchState]:
        main_switches = [
            peripheral
            for peripheral in self._peripheral_source()
            if isinstance(peripheral, BaseSwitch)
            and (include_fake_switches or not isinstance(peripheral, FakeSwitch))
        ]
        observables = [peripheral.observe for peripheral in main_switches]
        if not observables:
            return empty_node()
        merged = MergeNode.merge(*observables).map(
            PeripheralMessageEnvelope[SwitchState].unwrap_peripheral
        )
        return merged

    @cached_property
    def game_tick(self) -> GraphRouteStream[Any]:
        return GraphRouteStream(
            self._graph, runtime_route("game_tick", "HeartRuntimeGameTick")
        )

    @cached_property
    def window(self) -> GraphRouteStream[Any]:
        return GraphRouteStream(
            self._graph, runtime_route("window", "HeartRuntimeWindow")
        )

    @cached_property
    def clock(self) -> GraphRouteStream[Any]:
        return GraphRouteStream(
            self._graph, runtime_route("clock", "HeartRuntimeClock")
        )
