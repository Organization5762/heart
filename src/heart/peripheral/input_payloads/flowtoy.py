"""FlowToy packet payload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Mapping, MutableMapping

from heart.peripheral.core import Input

from .base import InputEventPayload, _normalize_timestamp


@dataclass(frozen=True, slots=True)
class FlowToyPacket(InputEventPayload):
    """FlowToy packet event that preserves the full bridge JSON body."""

    body: Mapping[str, Any]
    mode_name: str | None = None

    EVENT_TYPE: ClassVar[str] = "peripheral.flowtoy.packet"
    event_type: str = EVENT_TYPE

    def to_input(self, *, timestamp: datetime | None = None) -> Input:
        payload: MutableMapping[str, Any] = dict(self.body)
        if self.mode_name is not None:
            payload["mode_name"] = self.mode_name
        return Input(
            event_type=self.event_type,
            data=dict(payload),
            timestamp=_normalize_timestamp(timestamp),
        )
