from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from functools import cached_property
from typing import Any, Generic, Iterator, Mapping, Self, Sequence, TypeVar

import reactivex
from reactivex import operators as ops


@dataclass(slots=True)
class Input:
    """Normalized structure for messages emitted by peripherals."""

    event_type: str
    data: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

A = TypeVar("A")

class PeripheralGroup(StrEnum):
    MAIN_SWITCH = "MAIN_SWITCH"

@dataclass
class PeripheralWrapper(Generic[A]):
    data: A
    group: Sequence[PeripheralGroup] = field(default_factory=list)

    @classmethod
    def unwrap_peripheral(cls, wrapper: PeripheralWrapper[A]) -> A:
        return wrapper.data


class Peripheral(Generic[A]):
    """Abstract base class for all peripherals."""

    _logger = logging.getLogger(__name__)

    def _event_stream(self) -> reactivex.Observable[A]:
        # TODO: Implement
        return reactivex.empty()
        

    @cached_property
    def observe(
        self
    ) -> reactivex.Observable[PeripheralWrapper[A]]:
        def wrap(a: A) -> PeripheralWrapper[A]:
            return PeripheralWrapper[A](data=a)


        return self._event_stream().pipe(ops.map(wrap))

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

    def run(self) -> None:
        pass

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