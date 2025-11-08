"""Canonical payload helpers for peripherals emitting ``Input`` events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import (Any, ClassVar, Mapping, MutableMapping, Protocol,
                    runtime_checkable)

from heart.firmware_io.constants import (BUTTON_LONG_PRESS, BUTTON_PRESS,
                                         SWITCH_ROTATION)
from heart.peripheral.core import Input


def _normalize_timestamp(timestamp: datetime | None) -> datetime:
    if timestamp is None:
        return datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp


@runtime_checkable
class InputEventPayload(Protocol):
    """Protocol for payload helpers that can materialise :class:`Input`."""

    event_type: str

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
        """Render the payload as an :class:`Input` instance."""


@dataclass(frozen=True, slots=True)
class SwitchButton(InputEventPayload):
    """Represents a discrete button press on a rotary switch."""

    button: int
    pressed: bool
    long_press: bool = False
    EVENT_TYPE_PRESS: ClassVar[str] = BUTTON_PRESS
    EVENT_TYPE_LONG_PRESS: ClassVar[str] = BUTTON_LONG_PRESS

    @property
    def event_type(self) -> str:  # type: ignore[override]
        return self.EVENT_TYPE_LONG_PRESS if self.long_press else self.EVENT_TYPE_PRESS

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"button": self.button, "pressed": self.pressed},
            producer_id=producer_id,
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class SwitchRotation(InputEventPayload):
    """Represents the absolute rotary encoder position of a switch."""

    position: int

    EVENT_TYPE: ClassVar[str] = SWITCH_ROTATION
    event_type: str = EVENT_TYPE

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"position": int(self.position)},
            producer_id=producer_id,
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class MicrophoneLevel(InputEventPayload):
    """Aggregated loudness metrics for a captured audio block."""

    rms: float
    peak: float
    frames: int
    samplerate: int
    timestamp: float

    EVENT_TYPE: ClassVar[str] = "peripheral.microphone.level"
    event_type: str = EVENT_TYPE

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
        payload = {
            "rms": float(self.rms),
            "peak": float(self.peak),
            "frames": int(self.frames),
            "samplerate": int(self.samplerate),
            "timestamp": float(self.timestamp),
        }
        return Input(
            event_type=self.event_type,
            data=payload,
            producer_id=producer_id,
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class HeartRateMeasurement(InputEventPayload):
    """Normalized payload for ANT+ strap heart rate samples."""

    device_id: str
    bpm: int
    confidence: float | None = None
    battery_level: float | None = None

    EVENT_TYPE: ClassVar[str] = "peripheral.heart_rate.measurement"
    event_type: str = EVENT_TYPE

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
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
            producer_id=producer_id,
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

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
        payload: MutableMapping[str, Any] = {
            "device_id": self.device_id,
            "status": self.status,
        }
        if self.detail:
            payload.update(dict(self.detail))
        return Input(
            event_type=self.event_type,
            data=dict(payload),
            producer_id=producer_id,
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class AccelerometerVector(InputEventPayload):
    """Three-axis acceleration sample from the IMU peripheral."""

    x: float
    y: float
    z: float

    EVENT_TYPE: ClassVar[str] = "peripheral.accelerometer.vector"
    event_type: str = EVENT_TYPE

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"x": float(self.x), "y": float(self.y), "z": float(self.z)},
            producer_id=producer_id,
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class MagnetometerVector(InputEventPayload):
    """Three-axis magnetic field sample from the sensor bus."""

    x: float
    y: float
    z: float

    EVENT_TYPE: ClassVar[str] = "peripheral.magnetometer.vector"
    event_type: str = EVENT_TYPE

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"x": float(self.x), "y": float(self.y), "z": float(self.z)},
            producer_id=producer_id,
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class PhoneTextMessage(InputEventPayload):
    """Represents a BLE text payload received by the phone-text peripheral."""

    text: str

    EVENT_TYPE: ClassVar[str] = "peripheral.phone_text.message"
    event_type: str = EVENT_TYPE

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"text": self.text},
            producer_id=producer_id,
            timestamp=_normalize_timestamp(timestamp),
        )


__all__ = [
    "AccelerometerVector",
    "MagnetometerVector",
    "HeartRateLifecycle",
    "HeartRateMeasurement",
    "InputEventPayload",
    "MicrophoneLevel",
    "PhoneTextMessage",
    "SwitchButton",
    "SwitchRotation",
]
