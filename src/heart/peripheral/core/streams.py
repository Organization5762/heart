from __future__ import annotations

from functools import cached_property
from typing import Any, Callable, Generic, Iterable, TypeVar

from manyfold import (EmptyNode, Graph, Layer, OwnerName, Plane,
                      RouteRetentionPolicy, Schema, StreamFamily, StreamName,
                      StreamNode, TypedEnvelope, TypedRoute, Variant, route)
from manyfold.architecture import PubSubObservable
from manyfold.graph import RoutePipeline

from heart.peripheral.core import Peripheral, PeripheralMessageEnvelope
from heart.peripheral.switch import BaseSwitch, FakeSwitch, SwitchState

PeripheralSource = Callable[[], Iterable[Peripheral[Any]]]
RUNTIME_OWNER = OwnerName("heart.runtime")
RUNTIME_FAMILY = StreamFamily("runtime")
T = TypeVar("T")
LATEST_ONLY_RETENTION = RouteRetentionPolicy(
    latest_replay_policy="latest_only",
    replay_window="latest",
    payload_retention_policy="separate_store",
    history_limit=1,
)


def unwrap_stream_value(value: Any) -> Any:
    return value.value if isinstance(value, TypedEnvelope) else value


def _unwrap_stream_value(value: Any) -> Any:
    return unwrap_stream_value(value)


def _stream_from_source(source: Any) -> PubSubObservable:
    return PubSubObservable.merge(source).map(_unwrap_stream_value)


def _route_pipeline_do_action(
    self: RoutePipeline[Any],
    on_next: Callable[[Any], None] | None = None,
    *_args: Any,
    **_kwargs: Any,
) -> StreamNode[Any]:
    return _stream_from_source(self).do_action(on_next)


def _route_pipeline_start_with(
    self: RoutePipeline[Any], *values: Any
) -> StreamNode[Any]:
    return _stream_from_source(self).start_with(*values)


def _route_pipeline_scan(
    self: RoutePipeline[Any],
    accumulator: Callable[[Any, Any], Any],
    *,
    seed: Any = None,
) -> StreamNode[Any]:
    return _stream_from_source(self).scan(accumulator, seed=seed)


def _route_pipeline_pairwise(self: RoutePipeline[Any]) -> StreamNode[Any]:
    return _stream_from_source(self).pairwise()


def _route_pipeline_take(self: RoutePipeline[Any], count: int) -> StreamNode[Any]:
    return _stream_from_source(self).take(count)


def _route_pipeline_with_latest_from(
    self: RoutePipeline[Any], *sources: Any
) -> StreamNode[Any]:
    return _stream_from_source(self).with_latest_from(*sources)


def _route_pipeline_flat_map(
    self: RoutePipeline[Any], project: Callable[[Any], Any]
) -> StreamNode[Any]:
    return _stream_from_source(self).flat_map(project)


RoutePipeline.do_action = _route_pipeline_do_action  # type: ignore[attr-defined, method-assign]
RoutePipeline.start_with = _route_pipeline_start_with  # type: ignore[attr-defined, method-assign]
RoutePipeline.scan = _route_pipeline_scan  # type: ignore[attr-defined, method-assign]
RoutePipeline.pairwise = _route_pipeline_pairwise  # type: ignore[attr-defined, method-assign]
RoutePipeline.take = _route_pipeline_take  # type: ignore[attr-defined, method-assign]
RoutePipeline.with_latest_from = _route_pipeline_with_latest_from  # type: ignore[attr-defined, method-assign]
RoutePipeline.flat_map = _route_pipeline_flat_map  # type: ignore[attr-defined, method-assign]


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
        self._graph.configure_retention(route_ref, LATEST_ONLY_RETENTION)

    @property
    def value(self) -> T | None:
        latest = self._graph.latest(self._route)
        return None if latest is None else latest.value

    def emit(self, value: T) -> None:
        publish_nowait = getattr(self._graph, "publish_nowait", None)
        if publish_nowait is None:
            self._graph.publish(self._route, value)
            return
        publish_nowait(self._route, value)

    def on_next(self, value: T) -> None:
        self.emit(value)

    def subscribe(self, *args: Any, **kwargs: Any) -> Any:
        return self._observable().subscribe(*args, **kwargs)

    def pipe(self, *operators: Any) -> StreamNode[Any]:
        return self._observable().pipe(*operators)

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
        del name
        return _stream_from_source(self).map(transform)

    def filter(self, predicate: Callable[[T], bool], *, name: str | None = None) -> Any:
        del name
        return _stream_from_source(self).filter(predicate)

    def do_action(
        self,
        on_next: Callable[[T], None] | None = None,
        *_args: Any,
        **_kwargs: Any,
    ) -> StreamNode[T]:
        return _stream_from_source(self).do_action(on_next)

    def scan(self, accumulator: Callable[[Any, T], Any], *, seed: Any = None) -> Any:
        return _stream_from_source(self).scan(accumulator, seed=seed)

    def start_with(self, value: Any) -> Any:
        return _stream_from_source(self).start_with(value)

    def distinct_until_changed(self) -> StreamNode[T]:
        return _stream_from_source(self).distinct_until_changed()

    def pairwise(self) -> Any:
        return _stream_from_source(self).pairwise()

    def take(self, count: int) -> StreamNode[T]:
        return _stream_from_source(self).take(count)

    def with_latest_from(self, *sources: Any) -> Any:
        return _stream_from_source(self).with_latest_from(*sources)

    def flat_map(self, project: Callable[[T], Any]) -> Any:
        return _stream_from_source(self).flat_map(project)

    def switch_latest(self) -> Any:
        return _stream_from_source(self).switch_latest()

    def _observable(self) -> PubSubObservable:
        def subscribe(
            callback: Callable[[object], object],
            replay_latest: bool,
        ) -> Any:
            return self.callback(callback, replay_latest=replay_latest)

        return PubSubObservable(subscribe_factory=subscribe)


class PeripheralStreams:
    """Build shared event streams for detected peripherals."""

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
            return EmptyNode().observable()
        merged = PubSubObservable.merge(*observables).map(
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
