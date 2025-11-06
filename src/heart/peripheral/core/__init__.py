from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Self

from .event_bus import EventBus


@dataclass(slots=True)
class Input:
    """Normalized structure for messages emitted by peripherals."""

    event_type: str
    data: Any
    producer_id: int = 0


class Peripheral(abc.ABC):
    """Abstract base class for all peripherals."""

    _logger = logging.getLogger(__name__)
    _event_bus: EventBus | None = None

    def __init__(self, *, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    @abc.abstractmethod
    def run(self) -> None:
        """Start the peripheral's processing loop."""

    @classmethod
    def detect(cls) -> Iterator[Self]:
        raise NotImplementedError("'detect' is not implemented")

    @property
    def event_bus(self) -> EventBus | None:
        return self._event_bus

    def attach_event_bus(self, event_bus: EventBus) -> None:
        """Attach ``event_bus`` and notify subclasses."""

        self._event_bus = event_bus
        self._on_event_bus_attached()

    def _on_event_bus_attached(self) -> None:
        """Hook for subclasses that need to subscribe to the bus."""

    def emit_event(self, event_type: str, data: Any, *, producer_id: int = 0) -> None:
        """Publish an event to the shared bus if available."""

        if self._event_bus is None:
            return
        self._event_bus.emit(event_type, data, producer_id=producer_id)

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
