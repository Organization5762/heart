"""Shared state store for the input event bus."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Dict, Iterator, Mapping, MutableMapping

from heart.peripheral import Input


@dataclass(frozen=True, slots=True)
class StateEntry:
    """Immutable representation of the latest event for a producer."""

    event_type: str
    producer_id: int
    data: Any
    timestamp: datetime


class StateSnapshot(Mapping[str, Mapping[int, StateEntry]]):
    """Read-only materialized view of the store."""

    def __init__(self, state: Mapping[str, Mapping[int, StateEntry]]) -> None:
        copied: Dict[str, Mapping[int, StateEntry]] = {}
        for event_type, entries in state.items():
            copied[event_type] = MappingProxyType(dict(entries))
        self._state = MappingProxyType(copied)

    def __getitem__(self, key: str) -> Mapping[int, StateEntry]:
        return self._state[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._state)

    def __len__(self) -> int:
        return len(self._state)


class StateStore:
    """Tracks the latest :class:`Input` emitted per event type/producer."""

    def __init__(self) -> None:
        self._state: MutableMapping[str, MutableMapping[int, StateEntry]] = defaultdict(dict)

    @staticmethod
    def _normalize_timestamp(timestamp: datetime | None) -> datetime:
        if timestamp is None:
            return datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp

    def update(self, event: Input) -> StateEntry:
        """Record ``event`` as the latest value for its type and producer."""

        timestamp = self._normalize_timestamp(event.timestamp)
        entry = StateEntry(
            event_type=event.event_type,
            producer_id=event.producer_id,
            data=event.data,
            timestamp=timestamp,
        )
        bucket = self._state[event.event_type]
        bucket[event.producer_id] = entry
        return entry

    def get_latest(self, event_type: str, producer_id: int | None = None) -> StateEntry | None:
        """Return the latest entry for ``event_type`` and ``producer_id``."""

        bucket = self._state.get(event_type)
        if not bucket:
            return None
        if producer_id is not None:
            return bucket.get(producer_id)
        return max(bucket.values(), key=lambda entry: entry.timestamp, default=None)

    def get_all(self, event_type: str) -> Mapping[int, StateEntry]:
        """Return a read-only mapping of all producers for ``event_type``."""

        bucket = self._state.get(event_type)
        if not bucket:
            return MappingProxyType({})
        return MappingProxyType(dict(bucket))

    def snapshot(self) -> StateSnapshot:
        """Capture the current state for thread-safe inspection."""

        return StateSnapshot(self._state)

    def __len__(self) -> int:
        return sum(len(bucket) for bucket in self._state.values())
