"""Shared types and helpers for peripheral input payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol, runtime_checkable

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
