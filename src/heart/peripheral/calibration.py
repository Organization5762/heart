"""Calibration helpers for sensor peripherals."""


import logging
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping, Sequence, cast

from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import (VirtualPeripheralContext,
                                             VirtualPeripheralDefinition,
                                             _VirtualPeripheral)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CalibrationProfile:
    """Linear calibration applied to sensor vectors.

    The profile applies the following transform to the input vector ``v``::

        calibrated = scale * (matrix @ (v - offset))

    where ``offset`` and ``scale`` are element-wise vectors. The default
    configuration only subtracts a bias so that repeated samples match an
    expected reference frame.
    """

    axes: Sequence[str] = ("x", "y", "z")
    offset: Sequence[float] | None = None
    scale: Sequence[float] | None = None
    matrix: Sequence[Sequence[float]] | None = None
    precision: int | None = None

    def __post_init__(self) -> None:
        size = len(tuple(self.axes))
        if size == 0:
            raise ValueError("CalibrationProfile.axes must not be empty")

        def _normalize_vector(values: Sequence[float] | None, default: float) -> tuple[float, ...]:
            if values is None:
                return tuple(default for _ in range(size))
            if len(values) != size:
                raise ValueError(
                    "CalibrationProfile component length must match axes"
                )
            return tuple(float(value) for value in values)

        object.__setattr__(self, "axes", tuple(self.axes))
        object.__setattr__(self, "offset", _normalize_vector(self.offset, 0.0))
        object.__setattr__(self, "scale", _normalize_vector(self.scale, 1.0))
        if self.matrix is not None:
            rows = tuple(tuple(float(value) for value in row) for row in self.matrix)
            if len(rows) != size or any(len(row) != size for row in rows):
                raise ValueError("CalibrationProfile.matrix must be square")
            object.__setattr__(self, "matrix", rows)
        else:
            object.__setattr__(self, "matrix", None)

    @classmethod
    def from_reference(
        cls,
        *,
        raw: Mapping[str, float],
        expected: Mapping[str, float],
        axes: Iterable[str] = ("x", "y", "z"),
        precision: int | None = None,
    ) -> "CalibrationProfile":
        """Construct a profile that neutralises the bias between two readings."""

        axes_tuple = tuple(axes)
        if not axes_tuple:
            raise ValueError("axes must not be empty")

        offsets = []
        for axis in axes_tuple:
            try:
                bias = float(raw[axis]) - float(expected[axis])
            except KeyError as exc:
                raise KeyError(f"Missing axis {axis!r} in reference sample") from exc
            offsets.append(bias)
        return cls(axes=axes_tuple, offset=offsets, precision=precision)

    def describe(self) -> Mapping[str, Any]:
        """Return a serialisable description of the calibration profile."""

        offset = cast(tuple[float, ...], self.offset)
        scale = cast(tuple[float, ...], self.scale)
        payload: MutableMapping[str, Any] = {
            "axes": list(self.axes),
            "offset": list(offset),
            "scale": list(scale),
        }
        matrix = cast(tuple[tuple[float, ...], ...] | None, self.matrix)
        if matrix is not None:
            payload["matrix"] = [list(row) for row in matrix]
        if self.precision is not None:
            payload["precision"] = int(self.precision)
        return payload

    def apply(self, payload: Mapping[str, Any]) -> dict[str, float]:
        """Apply the calibration to ``payload`` and return a new mapping."""

        offset = cast(tuple[float, ...], self.offset)
        vector = []
        for axis in self.axes:
            try:
                vector.append(float(payload[axis]))
            except KeyError as exc:
                raise KeyError(f"Missing axis {axis!r} in payload") from exc
        adjusted = [value - bias for value, bias in zip(vector, offset)]

        matrix = cast(tuple[tuple[float, ...], ...] | None, self.matrix)
        if matrix is not None:
            transformed = []
            for row in matrix:
                transformed.append(sum(coef * value for coef, value in zip(row, adjusted)))
        else:
            transformed = adjusted

        scale = cast(tuple[float, ...], self.scale)
        scaled = [value * gain for value, gain in zip(transformed, scale)]

        if self.precision is not None:
            scaled = [round(value, self.precision) for value in scaled]

        return {axis: value for axis, value in zip(self.axes, scaled)}


class _CalibratedVirtualPeripheral(_VirtualPeripheral):
    """Virtual peripheral that rewrites sensor payloads using calibration."""

    def __init__(
        self,
        context: VirtualPeripheralContext,
        *,
        calibrations: Mapping[str, CalibrationProfile],
        output_event_types: Mapping[str, str],
        output_producer_id: int | None,
        passthrough_fields: Mapping[str, Sequence[str]],
        include_source_event: bool,
        include_raw_payload: bool,
    ) -> None:
        super().__init__(context)
        self._calibrations = dict(calibrations)
        self._output_event_types = dict(output_event_types)
        self._output_producer_id = output_producer_id
        self._passthrough_fields = {
            event_type: tuple(fields)
            for event_type, fields in passthrough_fields.items()
        }
        self._include_source_event = include_source_event
        self._include_raw_payload = include_raw_payload

    def handle(self, event: Input) -> None:
        profile = self._calibrations.get(event.event_type)
        if profile is None:
            return
        data = event.data
        if not isinstance(data, MappingABC):
            LOGGER.debug(
                "Calibration peripheral %s received non-mapping payload for %s",
                self._context.definition.name,
                event.event_type,
            )
            return
        try:
            corrected = profile.apply(data)
        except Exception:  # pragma: no cover - defensive logging
            LOGGER.exception(
                "Calibration peripheral %s failed to calibrate event %s",
                self._context.definition.name,
                event.event_type,
            )
            return

        payload: dict[str, Any] = dict(corrected)
        fields = self._passthrough_fields.get(event.event_type)
        if fields is None:
            fields = ()
        for field in fields:
            if field in data and field not in payload:
                payload[field] = data[field]
        if self._include_raw_payload and "raw" not in payload:
            payload["raw"] = dict(data)
        if "calibration" not in payload:
            payload["calibration"] = profile.describe()
        if self._include_source_event and "source_event" not in payload:
            payload["source_event"] = VirtualPeripheralContext.describe(event)

        output_event_type = self._output_event_types.get(event.event_type, event.event_type)
        producer_id = self._output_producer_id or event.producer_id
        self._context.emit(output_event_type, payload, producer_id=producer_id)

    def shutdown(self) -> None:  # pragma: no cover - nothing to release
        self._passthrough_fields.clear()


def calibrated_virtual_peripheral(
    *,
    name: str,
    calibrations: Mapping[str, CalibrationProfile],
    output_event_type: str | Mapping[str, str] | None = None,
    output_producer_id: int | None = None,
    priority: int = 0,
    metadata: Mapping[str, Any] | None = None,
    passthrough_fields: Sequence[str] | Mapping[str, Sequence[str]] | None = None,
    include_source_event: bool = False,
    include_raw_payload: bool = False,
) -> VirtualPeripheralDefinition:
    """Create a virtual peripheral that emits calibrated sensor events."""

    if not calibrations:
        raise ValueError("calibrations must not be empty")

    event_types = tuple(dict.fromkeys(calibrations.keys()))

    if isinstance(output_event_type, str):
        output_event_types = {event: output_event_type for event in event_types}
    elif output_event_type is None:
        output_event_types = {event: event for event in event_types}
    else:
        missing = set(calibrations) - set(output_event_type)
        if missing:
            raise KeyError(
                f"Missing output event type mapping for: {sorted(missing)}"
            )
        output_event_types = dict(output_event_type)

    if passthrough_fields is None:
        passthrough_map: dict[str, tuple[str, ...]] = {
            event: () for event in event_types
        }
    elif isinstance(passthrough_fields, Mapping):
        passthrough_map = {
            event: tuple(passthrough_fields.get(event, ())) for event in event_types
        }
    else:
        passthrough_map = {
            event: tuple(passthrough_fields) for event in event_types
        }

    def factory(context: VirtualPeripheralContext) -> _CalibratedVirtualPeripheral:
        return _CalibratedVirtualPeripheral(
            context,
            calibrations=calibrations,
            output_event_types=output_event_types,
            output_producer_id=output_producer_id,
            passthrough_fields=passthrough_map,
            include_source_event=include_source_event,
            include_raw_payload=include_raw_payload,
        )

    return VirtualPeripheralDefinition(
        name=name,
        event_types=event_types,
        factory=factory,
        priority=priority,
        metadata=metadata,
    )