from __future__ import annotations

from collections.abc import Iterable
from typing import Callable, Generic, TypeVar

from manyfold.graph import ObserverLike, SubscriptionLike

T = TypeVar("T")
SubscribeCallback = Callable[[ObserverLike[T], object | None], SubscriptionLike]


class CompositeSubscription:
    def __init__(self, subscriptions: Iterable[SubscriptionLike] = ()) -> None:
        self._subscriptions = tuple(subscriptions)
        self._disposed = False

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        for subscription in self._subscriptions:
            subscription.dispose()


class NoopSubscription:
    def dispose(self) -> None:
        return None


class CallbackSubscription:
    def __init__(self, dispose: Callable[[], None]) -> None:
        self._dispose = dispose
        self._disposed = False

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._dispose()


class _CallbackObserver(Generic[T]):
    def __init__(
        self,
        on_next: Callable[[T], None],
        on_error: Callable[[Exception], None] | None = None,
        on_completed: Callable[[], None] | None = None,
    ) -> None:
        self.on_next = on_next
        self.on_error = on_error or self._ignore_error
        self.on_completed = on_completed or self._ignore_completed

    def _ignore_error(self, _error: Exception) -> None:
        return None

    def _ignore_completed(self) -> None:
        return None


class CallbackObservable(Generic[T]):
    """ObservableLike adapter for callback-based Heart and Manyfold bridges."""

    def __init__(self, subscribe: SubscribeCallback[T]) -> None:
        self._subscribe = subscribe

    def subscribe(
        self,
        observer: ObserverLike[T] | Callable[[T], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_completed: Callable[[], None] | None = None,
        scheduler: object | None = None,
        *,
        on_next: Callable[[T], None] | None = None,
    ) -> SubscriptionLike:
        callback = on_next or observer
        if callback is None:
            observer = _CallbackObserver(lambda _value: None, on_error, on_completed)
        elif callable(callback):
            observer = _CallbackObserver(callback, on_error, on_completed)
        else:
            observer = callback
        return self._subscribe(observer, scheduler)
