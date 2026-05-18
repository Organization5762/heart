from __future__ import annotations

from functools import cached_property
from threading import Lock
from typing import Any, Callable, Generic, Iterable, TypeVar, cast

from manyfold import (EmptyNode, Graph, Layer, MergeNode, OwnerName, Plane,
                      RouteRetentionPolicy, Schema, StreamFamily, StreamName,
                      StreamNode, TypedEnvelope, TypedRoute, Variant, route)
from manyfold.graph import RoutePipeline

from heart.peripheral.core import Peripheral, PeripheralMessageEnvelope
from heart.peripheral.core.subscriptions import (CallbackObservable,
                                                 CompositeSubscription)
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


def _subscribe_source(source: Any, observer: Any) -> Any:
    def emit(value: Any) -> None:
        observer.on_next(_unwrap_stream_value(value))

    return source.subscribe(emit, observer.on_error, observer.on_completed)


def _stream_from_source(source: Any) -> "_DerivedStream":
    return _DerivedStream(lambda observer: _subscribe_source(source, observer))


def _materialize_stream(source: Any) -> StreamNode[Any]:
    return cast(StreamNode[Any], _MaterializedStream(source))


def combine_latest(*sources: Any) -> StreamNode[tuple[Any, ...]]:
    """Combine source streams without depending on reactivex source internals."""

    def subscribe(observer: Any) -> Any:
        source_count = len(sources)
        values = [None] * source_count
        has_value = [False] * source_count
        is_done = [False] * source_count
        lock = Lock()

        def subscribe_source(index: int, source: Any) -> Any:
            def on_next(value: Any) -> None:
                with lock:
                    values[index] = _unwrap_stream_value(value)
                    has_value[index] = True
                    if all(has_value):
                        observer.on_next(tuple(values))

            def on_completed() -> None:
                with lock:
                    is_done[index] = True
                    if all(is_done):
                        observer.on_completed()

            return source.subscribe(on_next, observer.on_error, on_completed)

        return CompositeSubscription(
            subscribe_source(index, source) for index, source in enumerate(sources)
        )

    return cast(
        StreamNode[tuple[Any, ...]], _materialize_stream(_DerivedStream(subscribe))
    )


class EventStream(Generic[T]):
    """Small Heart-owned push stream for event producers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: dict[int, Any] = {}
        self._next_subscription_id = 0

    @property
    def lock(self) -> Lock:
        return self._lock

    def emit(self, value: T) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers.values())
        for subscriber in subscribers:
            subscriber(value)

    def observable(self) -> StreamNode[T]:
        return cast(StreamNode[T], self)

    def subscribe(
        self,
        observer: Callable[[T], None] | Any | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_completed: Callable[[], None] | None = None,
        scheduler: object | None = None,
        *,
        on_next: Callable[[T], None] | None = None,
    ) -> Any:
        del on_error, on_completed, scheduler
        callback = on_next or observer
        if callback is None:

            def callback(_value: T) -> None:
                return None

        if not callable(callback):
            callback = callback.on_next
        with self._lock:
            subscription_id = self._next_subscription_id
            self._next_subscription_id += 1
            self._subscribers[subscription_id] = callback
        return _EventStreamSubscription(self, subscription_id)

    def pipe(self, *operators: Any) -> StreamNode[Any]:
        stream: Any = self
        for operator in operators:
            stream = operator(stream)
        return stream

    def map(self, transform: Callable[[T], Any], *, name: str | None = None) -> Any:
        del name
        return _materialize_stream(
            _DerivedStream(
                lambda observer: self.subscribe(
                    lambda value: observer.on_next(transform(value)),
                    observer.on_error,
                    observer.on_completed,
                )
            )
        )

    def filter(self, predicate: Callable[[T], bool], *, name: str | None = None) -> Any:
        del name

        def subscribe(observer: Any) -> Any:
            def on_next(value: T) -> None:
                if predicate(value):
                    observer.on_next(value)

            return self.subscribe(on_next, observer.on_error, observer.on_completed)

        return _materialize_stream(_DerivedStream(subscribe))

    def do_action(
        self,
        on_next: Callable[[T], None] | None = None,
        *_args: Any,
        **_kwargs: Any,
    ) -> StreamNode[T]:
        def subscribe(observer: Any) -> Any:
            def emit(value: T) -> None:
                if on_next is not None:
                    on_next(value)
                observer.on_next(value)

            return self.subscribe(emit, observer.on_error, observer.on_completed)

        return cast(StreamNode[T], _materialize_stream(_DerivedStream(subscribe)))

    def scan(self, accumulator: Callable[[Any, T], Any], *, seed: Any = None) -> Any:
        def subscribe(observer: Any) -> Any:
            state = seed

            def emit(value: T) -> None:
                nonlocal state
                state = accumulator(state, value)
                observer.on_next(state)

            return self.subscribe(emit, observer.on_error, observer.on_completed)

        return _materialize_stream(_DerivedStream(subscribe))

    def start_with(self, value: Any) -> Any:
        def subscribe(observer: Any) -> Any:
            observer.on_next(value)
            return self.subscribe(
                observer.on_next, observer.on_error, observer.on_completed
            )

        return _materialize_stream(_DerivedStream(subscribe))

    def distinct_until_changed(self) -> StreamNode[T]:
        def subscribe(observer: Any) -> Any:
            sentinel = object()
            previous: Any = sentinel

            def emit(value: T) -> None:
                nonlocal previous
                if previous is sentinel or value != previous:
                    previous = value
                    observer.on_next(value)

            return self.subscribe(emit, observer.on_error, observer.on_completed)

        return cast(StreamNode[T], _materialize_stream(_DerivedStream(subscribe)))

    def pairwise(self) -> Any:
        def subscribe(observer: Any) -> Any:
            sentinel = object()
            previous: Any = sentinel

            def emit(value: T) -> None:
                nonlocal previous
                if previous is not sentinel:
                    observer.on_next((previous, value))
                previous = value

            return self.subscribe(emit, observer.on_error, observer.on_completed)

        return _materialize_stream(_DerivedStream(subscribe))

    def take(self, count: int) -> StreamNode[T]:
        def subscribe(observer: Any) -> Any:
            seen = 0
            subscription: Any | None = None

            def emit(value: T) -> None:
                nonlocal seen
                if seen >= count:
                    return
                seen += 1
                observer.on_next(value)
                if seen >= count and subscription is not None:
                    subscription.dispose()

            subscription = self.subscribe(
                emit, observer.on_error, observer.on_completed
            )
            return subscription

        return cast(StreamNode[T], _materialize_stream(_DerivedStream(subscribe)))

    def with_latest_from(self, *sources: Any) -> Any:
        def subscribe(observer: Any) -> Any:
            latest: list[Any] = [None] * len(sources)
            ready = [False] * len(sources)
            subscriptions = [
                source.subscribe(
                    lambda value, index=index: _record_latest(
                        latest, ready, index, value
                    ),
                    observer.on_error,
                    observer.on_completed,
                )
                for index, source in enumerate(sources)
            ]

            def emit(value: T) -> None:
                if all(ready):
                    observer.on_next((value, *latest))

            subscriptions.append(
                self.subscribe(emit, observer.on_error, observer.on_completed)
            )
            return _CompositeSubscription(subscriptions)

        return _materialize_stream(_DerivedStream(subscribe))

    def flat_map(self, project: Callable[[T], Any]) -> Any:
        def subscribe(observer: Any) -> Any:
            subscriptions: list[Any] = []

            def emit(value: T) -> None:
                inner = project(value)
                subscriptions.append(
                    inner.subscribe(
                        observer.on_next, observer.on_error, observer.on_completed
                    )
                )

            subscriptions.append(
                self.subscribe(emit, observer.on_error, observer.on_completed)
            )
            return _CompositeSubscription(subscriptions)

        return _materialize_stream(_DerivedStream(subscribe))

    def switch_latest(self) -> Any:
        def subscribe(observer: Any) -> Any:
            active_subscription: Any | None = None

            def emit(inner: Any) -> None:
                nonlocal active_subscription
                if active_subscription is not None:
                    active_subscription.dispose()
                active_subscription = inner.subscribe(
                    observer.on_next, observer.on_error, observer.on_completed
                )

            outer_subscription = self.subscribe(
                emit, observer.on_error, observer.on_completed
            )
            return _SwitchLatestSubscription(
                lambda: active_subscription, outer_subscription
            )

        return _materialize_stream(_DerivedStream(subscribe))

    def callback(
        self, receive: Callable[[T], None], *, name: str | None = None
    ) -> _CallbackConnection:
        del name
        return _CallbackConnection(self.subscribe(receive))

    def _unsubscribe(self, subscription_id: int) -> None:
        with self._lock:
            self._subscribers.pop(subscription_id, None)


class _EventStreamSubscription:
    def __init__(self, stream: EventStream[Any], subscription_id: int) -> None:
        self._stream = stream
        self._subscription_id = subscription_id
        self._disposed = False

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._stream._unsubscribe(self._subscription_id)


class _Observer:
    def __init__(
        self,
        on_next: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None = None,
        on_completed: Callable[[], None] | None = None,
    ) -> None:
        self.on_next = on_next
        self.on_error = on_error or (lambda _error: None)
        self.on_completed = on_completed or (lambda: None)


class _CompositeSubscription:
    def __init__(self, subscriptions: Iterable[Any]) -> None:
        self._subscriptions = tuple(subscriptions)

    def dispose(self) -> None:
        for subscription in self._subscriptions:
            subscription.dispose()


class _SwitchLatestSubscription:
    def __init__(
        self, active_subscription: Callable[[], Any | None], outer_subscription: Any
    ) -> None:
        self._active_subscription = active_subscription
        self._outer_subscription = outer_subscription

    def dispose(self) -> None:
        self._outer_subscription.dispose()
        active_subscription = self._active_subscription()
        if active_subscription is not None:
            active_subscription.dispose()


class _CallbackConnection:
    def __init__(self, subscription: Any) -> None:
        self._subscription = subscription

    def remove(self) -> None:
        self._subscription.dispose()

    def dispose(self) -> None:
        self.remove()


class _NoopSubscription:
    def dispose(self) -> None:
        return None


def _record_latest(
    latest: list[Any], ready: list[bool], index: int, value: Any
) -> None:
    latest[index] = value
    ready[index] = True


class _DerivedStream(EventStream[Any]):
    def __init__(self, subscribe: Callable[[Any], Any]) -> None:
        super().__init__()
        self._subscribe = subscribe

    def subscribe(
        self,
        observer: Callable[[Any], None] | Any | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_completed: Callable[[], None] | None = None,
        scheduler: object | None = None,
        *,
        on_next: Callable[[Any], None] | None = None,
    ) -> Any:
        del scheduler
        callback = on_next or observer
        if callback is None:

            def callback(_value: Any) -> None:
                return None

        if callable(callback):
            wrapped = _Observer(callback, on_error, on_completed)
        else:
            wrapped = callback
        return self._subscribe(wrapped)


class _MaterializedStream(EventStream[Any]):
    def __init__(self, source: Any) -> None:
        super().__init__()
        self._source = source
        self._source_subscription: Any | None = None

    def subscribe(
        self,
        observer: Callable[[Any], None] | Any | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_completed: Callable[[], None] | None = None,
        scheduler: object | None = None,
        *,
        on_next: Callable[[Any], None] | None = None,
    ) -> Any:
        subscription = super().subscribe(
            observer,
            on_error,
            on_completed,
            scheduler,
            on_next=on_next,
        )
        if self._source_subscription is None:
            self._source_subscription = self._source.subscribe(
                self.emit, on_error, on_completed
            )
        return subscription

    def _unsubscribe(self, subscription_id: int) -> None:
        super()._unsubscribe(subscription_id)
        with self._lock:
            has_subscribers = bool(self._subscribers)
        if has_subscribers or self._source_subscription is None:
            return
        self._source_subscription.dispose()
        self._source_subscription = None


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
    def subscribe(observer: Any) -> Any:
        for value in values:
            observer.on_next(value)
        return _subscribe_source(self, observer)

    return cast(StreamNode[Any], _materialize_stream(_DerivedStream(subscribe)))


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
        self._graph.publish(self._route, value)

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

    def _observable(self) -> StreamNode[T]:
        def subscribe(observer: Any, scheduler: Any = None) -> Any:
            del scheduler
            return self.callback(observer.on_next, replay_latest=True)

        return cast(StreamNode[T], CallbackObservable(subscribe))


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
