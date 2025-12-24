"""Payloads emitted by switch peripherals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

from heart.firmware_io.constants import (BUTTON_LONG_PRESS, BUTTON_PRESS,
                                         SWITCH_ROTATION)
from heart.peripheral.core import Input

from .base import InputEventPayload, _normalize_timestamp


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
