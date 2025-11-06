"""Local event bus for reactive peripheral integrations."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterable, List, MutableMapping, Optional

from . import Input
from .state_store import StateStore

_LOGGER = logging.getLogger(__name__)


EventCallback = Callable[["Input"], None]


@dataclass(frozen=True)
class SubscriptionHandle:
    """Opaque handle returned when subscribing to the bus."""

    event_type: Optional[str]
    callback: EventCallback
    priority: int
    sequence: int


class EventBus:
    """Synchronous pub/sub dispatcher for :class:`Input` events."""

    def __init__(self, *, state_store: StateStore | None = None) -> None:
        self._subscribers: MutableMapping[Optional[str], List[SubscriptionHandle]] = defaultdict(list)
        self._next_sequence = 0
        self._state_store = state_store or StateStore()

    # Public API ---------------------------------------------------------
    def subscribe(
        self,
        event_type: Optional[str],
        callback: EventCallback,
        *,
        priority: int = 0,
    ) -> SubscriptionHandle:
        """Register ``callback`` for ``event_type`` events."""

        handle = SubscriptionHandle(event_type, callback, priority, self._next_sequence)
        self._next_sequence += 1
        bucket = self._subscribers[event_type]
        bucket.append(handle)
        bucket.sort(key=lambda item: (-item.priority, item.sequence))
        return handle

    def unsubscribe(self, handle: SubscriptionHandle) -> None:
        """Remove ``handle`` from the bus if it is still registered."""

        bucket = self._subscribers.get(handle.event_type)
        if not bucket:
            return
        try:
            bucket.remove(handle)
        except ValueError:
            return
        if not bucket:
            self._subscribers.pop(handle.event_type, None)

    def emit(self, event: Input | str, /, data=None, *, producer_id: int = 0) -> None:
        """Emit an :class:`Input` instance to subscribed callbacks."""

        if _is_input_instance(event):
            input_event = event  # type: ignore[assignment]
        else:
            input_event = Input(event_type=event, data=data, producer_id=producer_id)
        self._state_store.update(input_event)
        for handle in self._iter_targets(input_event.event_type):
            try:
                handle.callback(input_event)
            except Exception:
                _LOGGER.exception(
                    "EventBus subscriber %s failed for event %s", handle.callback, input_event
                )

    def run_on_event(
        self, event_type: Optional[str], *, priority: int = 0
    ) -> Callable[[EventCallback], EventCallback]:
        """Decorator variant of :meth:`subscribe`."""

        def decorator(callback: EventCallback) -> EventCallback:
            self.subscribe(event_type, callback, priority=priority)
            return callback

        return decorator

    @property
    def state_store(self) -> StateStore:
        """Return the state store maintained by the bus."""

        return self._state_store

    # Internal helpers ---------------------------------------------------
    def _iter_targets(self, event_type: str) -> Iterable[SubscriptionHandle]:
        """Yield subscribers in priority order, including wildcards."""

        handles: List[SubscriptionHandle] = []
        wildcard = self._subscribers.get(None)
        if wildcard:
            handles.extend(wildcard)
        specific = self._subscribers.get(event_type)
        if specific:
            handles.extend(specific)
        for handle in sorted(handles, key=lambda item: (-item.priority, item.sequence)):
            yield handle


def _is_input_instance(event: object) -> bool:
    CoreInput = _+_class()
    return isinstance(event, CoreInput)


def _get_input_class():
    from . import Input as CoreInput

    return CoreInput
