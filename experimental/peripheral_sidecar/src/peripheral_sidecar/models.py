from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class RawPeripheralSnapshot:
    """Structured representation of a peripheral data sample."""

    source: str
    data: Mapping[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_payload(self) -> str:
        return json.dumps({
            "source": self.source,
            "timestamp": self.timestamp,
            "data": self._encode(self.data),
        })

    @staticmethod
    def _encode(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {k: RawPeripheralSnapshot._encode(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [RawPeripheralSnapshot._encode(v) for v in value]
        if hasattr(value, "__dict__"):
            return RawPeripheralSnapshot._encode(vars(value))
        return value


@dataclass(slots=True)
class ActionEvent:
    """High level action emitted by the sidecar service."""

    action: str
    payload: Mapping[str, Any]
    source: str
    timestamp: float = field(default_factory=time.time)

    def to_payload(self) -> str:
        return json.dumps({
            "action": self.action,
            "payload": RawPeripheralSnapshot._encode(self.payload),
            "source": self.source,
            "timestamp": self.timestamp,
        })


@dataclass(slots=True)
class PeripheralPollResult:
    raw_snapshots: list[RawPeripheralSnapshot]
    action_events: list[ActionEvent]

    @classmethod
    def empty(cls) -> "PeripheralPollResult":
        return cls(raw_snapshots=[], action_events=[])

    def extend(self, other: "PeripheralPollResult") -> None:
        self.raw_snapshots.extend(other.raw_snapshots)
        self.action_events.extend(other.action_events)
