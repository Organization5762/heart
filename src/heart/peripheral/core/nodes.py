from __future__ import annotations

from typing import Any, Callable, TypeVar, cast

from manyfold import StreamNode

from heart.peripheral.core.subscriptions import NoopSubscription

T = TypeVar("T")


class _EmptyStream:
    def subscribe(
        self,
        observer: Callable[[Any], None] | Any | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_completed: Callable[[], None] | None = None,
        scheduler: object | None = None,
        *,
        on_next: Callable[[Any], None] | None = None,
    ) -> NoopSubscription:
        del observer, on_error, scheduler, on_next
        if on_completed is not None:
            on_completed()
        return NoopSubscription()

    def pipe(self, *operators: Any) -> StreamNode[Any]:
        stream: Any = self
        for operator in operators:
            stream = operator(stream)
        return cast(StreamNode[Any], stream)

    def map(
        self, transform: Callable[[Any], Any], *, name: str | None = None
    ) -> StreamNode[Any]:
        del transform, name
        return cast(StreamNode[Any], self)

    def filter(
        self, predicate: Callable[[Any], bool], *, name: str | None = None
    ) -> StreamNode[Any]:
        del predicate, name
        return cast(StreamNode[Any], self)

    def do_action(
        self,
        on_next: Callable[[Any], None] | None = None,
        *_args: Any,
        **_kwargs: Any,
    ) -> StreamNode[Any]:
        del on_next
        return cast(StreamNode[Any], self)

    def scan(
        self, accumulator: Callable[[Any, Any], Any], *, seed: Any = None
    ) -> StreamNode[Any]:
        del accumulator, seed
        return cast(StreamNode[Any], self)

    def start_with(self, value: Any) -> StreamNode[Any]:
        return cast(StreamNode[Any], _SingleValueStream(value))

    def distinct_until_changed(self) -> StreamNode[Any]:
        return cast(StreamNode[Any], self)

    def pairwise(self) -> StreamNode[Any]:
        return cast(StreamNode[Any], self)

    def take(self, count: int) -> StreamNode[Any]:
        del count
        return cast(StreamNode[Any], self)

    def with_latest_from(self, *sources: Any) -> StreamNode[Any]:
        del sources
        return cast(StreamNode[Any], self)

    def flat_map(self, project: Callable[[Any], Any]) -> StreamNode[Any]:
        del project
        return cast(StreamNode[Any], self)

    def switch_latest(self) -> StreamNode[Any]:
        return cast(StreamNode[Any], self)


class _SingleValueStream(_EmptyStream):
    def __init__(self, value: Any) -> None:
        self._value = value

    def subscribe(
        self,
        observer: Callable[[Any], None] | Any | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_completed: Callable[[], None] | None = None,
        scheduler: object | None = None,
        *,
        on_next: Callable[[Any], None] | None = None,
    ) -> NoopSubscription:
        del on_error, scheduler
        callback = on_next or observer
        if callable(callback):
            callback(self._value)
        elif callback is not None:
            callback.on_next(self._value)
        if on_completed is not None:
            on_completed()
        return NoopSubscription()


def empty_node() -> StreamNode[T]:
    """Return a Manyfold node stream that intentionally emits no values."""
    return cast(StreamNode[T], _EmptyStream())
