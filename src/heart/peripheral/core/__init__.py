from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from functools import cached_property
from typing import Any, Generic, Iterator, Mapping, Self, Sequence, TypeVar

import manyfold.rx as reactivex
from manyfold.rx import operators as ops
from manyfold.sensor_io import (SensorEvent, SensorIdentity, SensorLocation,
                                SensorTag)

from heart.utilities.logging import get_logger


@dataclass(slots=True)
class Input:
    """Normalized structure for messages emitted by peripherals."""

    event_type: str
    data: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_sensor_event(
        self,
        *,
        identity: SensorIdentity | None = None,
        sequence_number: int | None = None,
    ) -> SensorEvent:
        return SensorEvent(
            event_type=self.event_type,
            data=self.data,
            observed_at=self.timestamp.timestamp(),
            identity=identity or SensorIdentity(),
            sequence_number=sequence_number,
        )


@dataclass(frozen=True, slots=True)
class InputDescriptor:
    """Describe an input a peripheral or provider expects to consume."""

    name: str
    stream: reactivex.Observable[Any]
    payload_type: type[Any] | None = None
    description: str | None = None

A = TypeVar("A")

class PeripheralGroup(StrEnum):
    MAIN_SWITCH = "MAIN_SWITCH"

@dataclass
class PeripheralTag:
    # Example of a tag specifying the input type
    # PeripheralTag(
    #     name="input_variant",
    #     variant="button",
    #     metadata={"version": "v1"}
    # )
    name: str
    variant: str
    metadata: dict[str, str] = field(default_factory=dict)

    def to_sensor_tag(self) -> SensorTag:
        return SensorTag(
            name=self.name,
            variant=self.variant,
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True, slots=True)
class PeripheralLocation:
    """Physical-space coordinate for a peripheral relative to the display."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    time: datetime | None = None

    def to_sensor_location(self) -> SensorLocation:
        return SensorLocation(
            x=self.x,
            y=self.y,
            z=self.z,
            timestamp=None if self.time is None else self.time.timestamp(),
        )


@dataclass
class PeripheralInfo:
    id: str | None = None
    tags: Sequence[PeripheralTag] = field(default_factory=list)
    location: PeripheralLocation = field(default_factory=PeripheralLocation)

    def to_sensor_identity(self) -> SensorIdentity:
        return SensorIdentity(
            id=self.id,
            tags=tuple(tag.to_sensor_tag() for tag in self.tags),
            location=self.location.to_sensor_location(),
        )

@dataclass
class PeripheralMessageEnvelope(Generic[A]):
    peripheral_info: PeripheralInfo
    data: A

    @classmethod
    def unwrap_peripheral(cls, wrapper: PeripheralMessageEnvelope[A]) -> A:
        return wrapper.data

    def to_sensor_event(
        self,
        *,
        event_type: str,
        observed_at: datetime | None = None,
        sequence_number: int | None = None,
    ) -> SensorEvent:
        timestamp = observed_at or datetime.now(timezone.utc)
        return SensorEvent(
            event_type=event_type,
            data=self.data,
            observed_at=timestamp.timestamp(),
            identity=self.peripheral_info.to_sensor_identity(),
            sequence_number=sequence_number,
        )

class Peripheral(Generic[A]):
    """Abstract base class for all peripherals."""

    _logger = get_logger(__name__)

    def _event_stream(self) -> reactivex.Observable[A]:
        return reactivex.empty()

    def peripheral_info(self) -> PeripheralInfo:
        # Default implementation returns a generic PeripheralInfo instance
        # with no identifier or tags. Subclasses should override this method
        # to supply meaningful identification and metadata relevant to their hardware.
        return PeripheralInfo()

    @cached_property
    def observe(
        self
    ) -> reactivex.Observable[PeripheralMessageEnvelope[A]]:
        def wrap(a: A) -> PeripheralMessageEnvelope[A]:
            return PeripheralMessageEnvelope[A](
                data=a,
                peripheral_info=self.peripheral_info()
            )

        return self._event_stream().pipe(
            ops.map(wrap),
            ops.share(),
        )

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
