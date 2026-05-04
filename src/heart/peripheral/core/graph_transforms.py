from __future__ import annotations

from itertools import count
from threading import Lock
from typing import Any, Callable, Generic, TypeVar, cast

from manyfold import (Graph, Layer, OwnerName, Plane, Schema, StreamFamily,
                      StreamName, StreamNode, TypedRoute, Variant, route)
from manyfold.graph import ObservableLike

from heart.peripheral.core.subscriptions import CallbackObservable

T = TypeVar("T")
TOut = TypeVar("TOut")
_TRANSFORM_IDS = count(1)


def graph_transform_route(name: str, schema_id: str) -> Any:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=OwnerName("heart.transforms"),
        family=StreamFamily("transform"),
        stream=StreamName(name),
        variant=Variant.State,
        schema=Schema.any(schema_id),
    )


def unique_graph_transform_route(name: str, schema_id: str) -> Any:
    transform_id = next(_TRANSFORM_IDS)
    return graph_transform_route(f"{name}.{transform_id}", schema_id)


class ManyfoldObservableTransform(Generic[T, TOut]):
    def __init__(
        self,
        source: ObservableLike[T],
        mapper: Callable[[T], TOut],
        *,
        name: str,
        schema_id: str,
    ) -> None:
        self._graph = Graph()
        self._source = source
        self._mapper = mapper
        self._source_route: TypedRoute[T] = unique_graph_transform_route(
            f"{name}.source",
            f"{schema_id}Source",
        )
        self._output_route: TypedRoute[TOut] = unique_graph_transform_route(
            f"{name}.output",
            f"{schema_id}Output",
        )
        self._lock = Lock()
        self._map_subscription: Any | None = None
        self._source_subscription: Any | None = None

    def observable(self) -> StreamNode[TOut]:
        def subscribe(observer: Any, scheduler: Any = None) -> Any:
            with self._lock:
                if self._map_subscription is None:
                    self._map_subscription = self._graph.stateful_map(
                        self._source_route,
                        initial_state=None,
                        step=lambda state, value: (state, self._mapper(value)),
                        output=self._output_route,
                    )

                output_subscription = self._graph.observe(
                    self._output_route,
                    replay_latest=False,
                ).callback(observer.on_next)

                if self._source_subscription is None:
                    self._source_subscription = self._graph.pipe(
                        cast(Any, self._source),
                        self._source_route,
                    )

            return output_subscription

        return cast(StreamNode[TOut], CallbackObservable(subscribe))
