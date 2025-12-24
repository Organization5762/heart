"""Radio payload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Mapping, MutableMapping, Sequence

from heart.firmware_io.constants import RADIO_PACKET
from heart.peripheral.core import Input

from .base import InputEventPayload, _normalize_timestamp


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
