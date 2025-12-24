"""Messaging payload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from heart.peripheral.core import Input

from .base import InputEventPayload, _normalize_timestamp


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
