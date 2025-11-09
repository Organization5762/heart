from __future__ import annotations

import abc
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterator, Mapping, Self

if TYPE_CHECKING:  # pragma: no cover - import-time convenience
    from .event_bus import EventBus as EventBus
    from .event_bus import SubscriptionHandle as SubscriptionHandle
    from .state_store import StateEntry as StateEntry
    from .state_store import StateSnapshot as StateSnapshot
    from .state_store import StateStore as StateStore


@dataclass(slots=True)
class Input:
    """Normalized structure for messages emitted by peripherals."""

    event_type: str
    data: Any
    producer_id: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Peripheral(abc.ABC):
    """Abstract base class for all peripherals."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._event_bus: EventBus | None = None
        self._event_bus_subscriptions: list[SubscriptionHandle] = []

    @abc.abstractmethod
    def run(self) -> None:
        """Start the peripheral's processing loop."""

    @property
    def event_bus(self) -> EventBus | None:
        self._ensure_event_bus_storage()
        return self._event_bus

    @classmethod
    def detect(cls) -> Iterator[Self]:
        raise NotImplementedError("'detect' is not implemented")

    def handle_input(self, input: Input) -> None:
        """Process input data sent to the peripheral.

        Subclasses can override this method to react to events emitted by
        other components.  The base implementation is intentionally a no-op to
        keep backwards compatibility with peripherals that do not yet
        implement input handling.
        """

    def update_due_to_data(self, data: Mapping[str, Any]) -> None:
        """Convert a raw payload into an :class:`Input` instance.

        Parameters
        ----------
        data:
            Mapping produced by external sources.  The mapping must contain at
            least the keys ``event_type`` and ``data``.  Additional keys are
            passed through to :class:`Input`.
        """

        try:
            self.handle_input(Input(**data))
        except TypeError:
            self._logger.debug(
                "Ignoring malformed peripheral payload: %s", data, exc_info=True
            )

    # ------------------------------------------------------------------
    # Event bus integration
    # ------------------------------------------------------------------
    def attach_event_bus(self, event_bus: EventBus) -> None:
        """Attach ``event_bus`` so the peripheral can participate in pub/sub."""

        self._ensure_event_bus_storage()
        if self._event_bus is event_bus:
            return

        if self._event_bus is not None:
            self._unsubscribe_all()

        self._event_bus = event_bus
        self._event_bus_subscriptions = []
        try:
            self.on_event_bus_attached(event_bus)
        except Exception:
            self._logger.exception(
                "Peripheral %s failed to attach to event bus", type(self).__name__
            )

    def detach_event_bus(self) -> None:
        """Remove the current event bus, if any, and unsubscribe callbacks."""

        self._ensure_event_bus_storage()
        if self._event_bus is None:
            return
        self._unsubscribe_all()
        self._event_bus = None

    def on_event_bus_attached(self, event_bus: EventBus) -> None:  # noqa: D401
        """Hook for subclasses to register event handlers."""

    def subscribe_event(
        self,
        event_type: str | None,
        callback: Callable[[Input], None],
        *,
        priority: int = 0,
    ) -> SubscriptionHandle:
        """Register ``callback`` for ``event_type`` and track the subscription."""

        bus = self._require_event_bus()
        handle = bus.subscribe(event_type, callback, priority=priority)
        self._event_bus_subscriptions.append(handle)
        return handle

    def emit_input(self, input_event: Input) -> None:
        """Publish ``input_event`` on the attached event bus, if present."""

        bus = self.event_bus
        if bus is None:
            self._logger.debug(
                "Peripheral %s dropped event %s due to missing bus",
                type(self).__name__,
                input_event.event_type,
            )
            return
        bus.emit(input_event)

    def emit_event(self, event_type: str, data: Any, *, producer_id: int = 0) -> None:
        """Publish a payload as an :class:`Input` if an event bus is attached."""

        bus = self.event_bus
        if bus is None:
            self._logger.debug(
                "Peripheral %s dropped payload %s due to missing bus",
                type(self).__name__,
                event_type,
            )
            return
        bus.emit(event_type, data, producer_id=producer_id)

    def _ensure_event_bus_storage(self) -> None:
        if not hasattr(self, "_event_bus_subscriptions"):
            self._event_bus_subscriptions = []
        if not hasattr(self, "_event_bus"):
            self._event_bus = None

    def _unsubscribe_all(self) -> None:
        bus = self._event_bus
        if bus is None:
            self._event_bus_subscriptions = []
            return
        for handle in list(self._event_bus_subscriptions):
            try:
                bus.unsubscribe(handle)
            except Exception:
                self._logger.exception(
                    "Failed to unsubscribe %s from event bus", handle.callback
                )
        self._event_bus_subscriptions = []

    def _require_event_bus(self) -> EventBus:
        bus = self.event_bus
        if bus is None:
            raise RuntimeError("Peripheral has no event bus attached")
        return bus


def __getattr__(name: str):
    if name in {"StateEntry", "StateSnapshot", "StateStore"}:
        from .state_store import StateEntry, StateSnapshot, StateStore

        return {"StateEntry": StateEntry, "StateSnapshot": StateSnapshot, "StateStore": StateStore}[name]
    raise AttributeError(name)
