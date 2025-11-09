"""Force sensor peripheral emitting normalized measurement events."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Mapping, cast

from heart.events.types import ForceMeasurement
from heart.peripheral.core import Input, Peripheral
from heart.peripheral.core.event_bus import EventBus
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

ForceKind = Literal["tensile", "magnetic"]

class ForcePeripheral(Peripheral):
    """Peripheral that converts force readings into bus events.

    The peripheral accepts normalized measurements describing either a tensile
    or magnetic force.  For each reading it emits a
    :class:`~heart.peripheral.core.Input` event using the
    :class:`~heart.events.types.ForceMeasurement` helper.
    """

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        producer_id: int | None = None,
    ) -> None:
        self._producer_id = producer_id if producer_id is not None else id(self)
        super().__init__()
        if event_bus is not None:
            self.attach_event_bus(event_bus)

    def run(self) -> None:
        """No background loop is required for the force peripheral."""

    def attach_event_bus(self, event_bus: EventBus) -> None:
        super().attach_event_bus(event_bus)

    def record_force(
        self,
        *,
        force_type: ForceKind,
        magnitude: float,
        unit: str | None = None,
        timestamp: datetime | None = None,
    ) -> Input:
        """Emit an event describing a single force reading.

        Parameters
        ----------
        force_type:
            Whether the force reading represents tensile or magnetic force.
        magnitude:
            Force magnitude parsed from the sensor.
        unit:
            Optional unit string.  Defaults to ``ForceMeasurement.DEFAULT_UNIT``
            when omitted.
        timestamp:
            Optional timestamp to use for the resulting event.
        """

        measurement = ForceMeasurement(
            magnitude=magnitude,
            force_type=force_type,
            unit=unit or ForceMeasurement.DEFAULT_UNIT,
        )
        event = measurement.to_input(
            producer_id=self._producer_id, timestamp=timestamp
        )
        self.emit_input(event)
        return event

    def update_due_to_data(self, data: Mapping[str, Any]) -> None:
        """Accept raw payloads and emit a normalized measurement event."""

        event_type = data.get("event_type")
        if event_type and event_type != ForceMeasurement.EVENT_TYPE:
            return

        payload: Any = data.get("data", data)
        if not isinstance(payload, Mapping):
            logger.debug("Ignoring malformed force payload: %s", payload)
            return

        try:
            force_type = str(payload["force_type"]).lower()
            magnitude = float(payload["magnitude"])
        except (KeyError, TypeError, ValueError):
            logger.debug("Force payload missing required fields: %s", payload)
            return

        unit_obj = payload.get("unit")
        unit = str(unit_obj) if unit_obj is not None else None

        try:
            normalized_type = cast(ForceKind, force_type)
            self.record_force(
                force_type=normalized_type, magnitude=magnitude, unit=unit
            )
        except ValueError:
            logger.debug("Rejected invalid force payload: %s", payload)

    def handle_input(self, input: Input) -> None:  # pragma: no cover - no-op hook
        return

