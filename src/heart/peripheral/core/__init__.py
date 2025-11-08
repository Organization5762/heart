import abc
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping, Self


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

    @abc.abstractmethod
    def run(self) -> None:
        """Start the peripheral's processing loop."""

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


def __getattr__(name: str):
    if name in {"StateEntry", "StateSnapshot", "StateStore"}:
        from .state_store import StateEntry, StateSnapshot, StateStore

        return {"StateEntry": StateEntry, "StateSnapshot": StateSnapshot, "StateStore": StateStore}[name]
    raise AttributeError(name)
