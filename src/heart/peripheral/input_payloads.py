"""Canonical payload helpers for peripherals emitting ``Input`` events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import (TYPE_CHECKING, Any, ClassVar, Literal, Mapping,
                    MutableMapping, Protocol, Sequence, runtime_checkable)

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    import pygame
    from PIL import Image

from heart.firmware_io.constants import (BUTTON_LONG_PRESS, BUTTON_PRESS,
                                         RADIO_PACKET, SWITCH_ROTATION)
from heart.peripheral.core import Input


def _normalize_timestamp(timestamp: datetime | None) -> datetime:
    if timestamp is None:
        return datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp


if TYPE_CHECKING:

    @runtime_checkable
    class InputEventPayload(Protocol):
        """Protocol for payload helpers that can materialise :class:`Input`."""

        event_type: str

        def to_input(self, *, timestamp: datetime | None = None) -> Input:
            """Render the payload as an :class:`Input` instance."""

else:

    class InputEventPayload:
        """Runtime shim so dataclass payloads remain instantiable."""

        __slots__ = ()


@dataclass(frozen=True, slots=True)
class SwitchButton(InputEventPayload):
    """Represents a discrete button press on a rotary switch."""

    button: int
    pressed: bool
    long_press: bool = False
    EVENT_TYPE_PRESS: ClassVar[str] = BUTTON_PRESS
    EVENT_TYPE_LONG_PRESS: ClassVar[str] = BUTTON_LONG_PRESS
    event_type: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_type",
            self.EVENT_TYPE_LONG_PRESS if self.long_press else self.EVENT_TYPE_PRESS,
        )

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"button": self.button, "pressed": self.pressed},
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class SwitchRotation(InputEventPayload):
    """Represents the absolute rotary encoder position of a switch."""

    position: int

    EVENT_TYPE: ClassVar[str] = SWITCH_ROTATION
    event_type: str = EVENT_TYPE

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"position": int(self.position)},
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

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
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
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class RadioPacket(InputEventPayload):
    """Raw 2.4 GHz transport packet emitted by a radio bridge."""

    frequency_hz: float | None = None
    channel: float | None = None
    modulation: str | None = None
    rssi_dbm: float | None = None
    payload: bytes | bytearray | Sequence[int] | str | None = None
    metadata: Mapping[str, Any] | None = None

    EVENT_TYPE: ClassVar[str] = RADIO_PACKET
    event_type: str = EVENT_TYPE

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        payload: MutableMapping[str, Any] = {}

        if self.frequency_hz is not None:
            payload["frequency_hz"] = float(self.frequency_hz)
        if self.channel is not None:
            payload["channel"] = float(self.channel)
        if self.modulation is not None:
            payload["modulation"] = str(self.modulation)
        if self.rssi_dbm is not None:
            payload["rssi_dbm"] = float(self.rssi_dbm)
        if self.payload is not None:
            payload["payload"] = self._normalise_payload(self.payload)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)

        return Input(
            event_type=self.event_type,
            data=dict(payload),
            timestamp=_normalize_timestamp(timestamp),
        )

    @staticmethod
    def _normalise_payload(
        payload: bytes | bytearray | Sequence[int] | str,
    ) -> list[int]:
        if isinstance(payload, (bytes, bytearray, memoryview)):
            return [int(b) & 0xFF for b in bytes(payload)]
        if isinstance(payload, str):
            return [int(b) & 0xFF for b in payload.encode("utf-8")]

        normalised: list[int] = []
        for item in payload:
            if not isinstance(item, int):
                raise TypeError("Radio payload sequences must contain integers")
            normalised.append(int(item) & 0xFF)
        return normalised


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


@dataclass(frozen=True, slots=True)
class PhoneTextMessage(InputEventPayload):
    """Represents a BLE text payload received by the phone-text peripheral."""

    text: str

    EVENT_TYPE: ClassVar[str] = "peripheral.phone_text.message"
    event_type: str = EVENT_TYPE

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data={"text": self.text},
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

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data=self,
            timestamp=_normalize_timestamp(timestamp),
        )


@dataclass(frozen=True, slots=True)
class RendererFrame(InputEventPayload):
    """Intermediate surface snapshot emitted by renderers."""

    channel: str
    renderer: str
    frame_id: int
    width: int
    height: int
    pixel_format: Literal["RGBA", "RGB", "ARGB", "BGRA"]
    data: bytes
    metadata: Mapping[str, Any] | None = None

    EVENT_TYPE: ClassVar[str] = "display.renderer.frame"
    event_type: str = EVENT_TYPE

    def __post_init__(self) -> None:
        if not self.channel:
            raise ValueError("RendererFrame channel must be a non-empty string")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("RendererFrame dimensions must be positive")
        if not self.pixel_format:
            raise ValueError("RendererFrame pixel_format must be provided")
        if not isinstance(self.data, (bytes, bytearray, memoryview)):
            raise TypeError("RendererFrame data must be a bytes-like object")
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise TypeError("RendererFrame metadata must be a mapping when provided")
        if isinstance(self.data, bytearray):
            object.__setattr__(self, "data", bytes(self.data))
        if isinstance(self.metadata, Mapping):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_surface(
        cls,
        channel: str,
        surface: "pygame.Surface",
        *,
        renderer: str,
        frame_id: int,
        pixel_format: Literal["RGBA", "RGB", "ARGB", "BGRA"] = "RGBA",
        metadata: Mapping[str, Any] | None = None,
    ) -> "RendererFrame":
        """Capture ``surface`` pixels into a :class:`RendererFrame` payload."""

        import pygame

        if not isinstance(surface, pygame.Surface):
            raise TypeError("surface must be a pygame.Surface instance")
        if pixel_format not in {"RGBA", "RGB", "ARGB", "BGRA"}:
            raise ValueError(f"Unsupported pixel format: {pixel_format}")
        width, height = surface.get_size()
        pixels = pygame.image.tostring(surface, pixel_format)
        return cls(
            channel=channel,
            renderer=renderer,
            frame_id=frame_id,
            width=width,
            height=height,
            pixel_format=pixel_format,
            data=pixels,
            metadata=metadata,
        )

    def to_surface(self) -> "pygame.Surface":
        """Materialize the stored buffer as a :class:`pygame.Surface`."""

        import pygame

        surface = pygame.image.frombuffer(
            self.data, (self.width, self.height), self.pixel_format
        )
        # frombuffer shares the underlying memory; copy to decouple from payload
        return surface.copy()

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        return Input(
            event_type=self.event_type,
            data=self,
            timestamp=_normalize_timestamp(timestamp),
        )
