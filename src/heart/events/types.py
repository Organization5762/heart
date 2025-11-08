"""Canonical payload helpers for peripherals emitting ``Input`` events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import (TYPE_CHECKING, Any, ClassVar, Mapping, MutableMapping,
                    Protocol, runtime_checkable)

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from PIL import Image

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


@dataclass(frozen=True, slots=True)
class DisplayFrame(InputEventPayload):
    """Raw image payload emitted by the LED matrix peripheral."""

    frame_id: int
    width: int
    height: int
    mode: str
    data: bytes
    metadata: Mapping[str, Any] | None = None

    EVENT_TYPE: ClassVar[str] = "peripheral.display.frame"
    event_type: str = EVENT_TYPE

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("DisplayFrame dimensions must be positive")
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise TypeError("DisplayFrame metadata must be a mapping when provided")
        if self.metadata is not None:
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_image(
        cls,
        image: Image.Image,
        *,
        frame_id: int,
        metadata: Mapping[str, Any] | None = None,
    ) -> "DisplayFrame":
        from PIL import Image

        if not isinstance(image, Image.Image):
            raise TypeError("image must be a PIL.Image.Image instance")
        return cls(
            frame_id=frame_id,
            width=image.width,
            height=image.height,
            mode=image.mode,
            data=image.tobytes(),
            metadata=metadata,
        )

    def to_image(self) -> Image.Image:
        from PIL import Image

        return Image.frombytes(self.mode, (self.width, self.height), self.data)

    def to_input(self, *, producer_id: int = 0, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data=self,
            producer_id=producer_id,
            timestamp=_normalize_timestamp(timestamp),
        )


__all__ = [
    "AccelerometerVector",
    "DisplayFrame",
    "HeartRateLifecycle",
    "HeartRateMeasurement",
    "InputEventPayload",
    "MicrophoneLevel",
    "PhoneTextMessage",
    "SwitchButton",
    "SwitchRotation",
]
