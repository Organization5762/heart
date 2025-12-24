"""Audio-related payload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from heart.peripheral.core import Input

from .base import InputEventPayload, _normalize_timestamp


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
