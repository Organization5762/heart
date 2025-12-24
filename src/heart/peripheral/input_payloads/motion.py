"""Motion-related payload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from heart.peripheral.core import Input

from .base import InputEventPayload, _normalize_timestamp


@dataclass(frozen=True, slots=True)
class AccelerometerVector(InputEventPayload):
    """Three-axis acceleration sample from the IMU peripheral."""

    x: float
    y: float
    z: float

    EVENT_TYPE: ClassVar[str] = "peripheral.accelerometer.vector"
    event_type: str = EVENT_TYPE

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"x": float(self.x), "y": float(self.y), "z": float(self.z)},
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class MagnetometerVector(InputEventPayload):
    """Three-axis magnetic field sample"""

    x: float
    y: float
    z: float

    EVENT_TYPE: ClassVar[str] = "peripheral.magnetometer.vector"
    event_type: str = EVENT_TYPE

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"x": float(self.x), "y": float(self.y), "z": float(self.z)},
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class ForceMeasurement(InputEventPayload):
    """Normalized payload describing a tensile or magnetic force reading."""

    magnitude: float
    force_type: str
    unit: str = "N"

    VALID_FORCE_TYPES: ClassVar[tuple[str, ...]] = ("tensile", "magnetic")
    DEFAULT_UNIT: ClassVar[str] = "N"
    EVENT_TYPE: ClassVar[str] = "peripheral.force.measurement"
    event_type: str = EVENT_TYPE

    def __post_init__(self) -> None:
        normalized = self.force_type.lower()
        if normalized not in self.VALID_FORCE_TYPES:
            raise ValueError(
                f"force_type must be one of {self.VALID_FORCE_TYPES}, got '{self.force_type}'"
            )
        if not self.unit:
            raise ValueError("unit must be a non-empty string")
        object.__setattr__(self, "force_type", normalized)

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        payload = {
            "type": self.force_type,
            "magnitude": float(self.magnitude),
            "unit": self.unit,
        }
        return Input(
            event_type=self.event_type,
            data=payload,
            timestamp=_normalize_timestamp(timestamp),
        )
