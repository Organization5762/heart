"""Biometric payload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Mapping, MutableMapping

from heart.peripheral.core import Input

from .base import InputEventPayload, _normalize_timestamp


@dataclass(frozen=True, slots=True)
class HeartRateMeasurement(InputEventPayload):
    """Normalized payload for ANT+ strap heart rate samples."""

    device_id: str
    bpm: int
    confidence: float | None = None
    battery_level: float | None = None

    EVENT_TYPE: ClassVar[str] = "peripheral.heart_rate.measurement"
    event_type: str = EVENT_TYPE

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        payload: MutableMapping[str, Any] = {
            "device_id": self.device_id,
            "bpm": int(self.bpm),
        }
        if self.confidence is not None:
            payload["confidence"] = float(self.confidence)
        if self.battery_level is not None:
            payload["battery_level"] = float(self.battery_level)
        return Input(
            event_type=self.event_type,
            data=dict(payload),
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class HeartRateLifecycle(InputEventPayload):
    """Lifecycle notification for ANT+ heart rate straps."""

    status: str
    device_id: str
    detail: Mapping[str, Any] | None = None

    EVENT_TYPE: ClassVar[str] = "peripheral.heart_rate.lifecycle"
    event_type: str = EVENT_TYPE

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        payload: MutableMapping[str, Any] = {
            "device_id": self.device_id,
            "status": self.status,
        }
        if self.detail:
            payload.update(dict(self.detail))
        return Input(
            event_type=self.event_type,
            data=dict(payload),
            timestamp=_normalize_timestamp(timestamp),
        )
