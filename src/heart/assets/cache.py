from __future__ import annotations

from collections import OrderedDict
from typing import Generic, Hashable, TypeVar

from heart.utilities.logging import get_logger

KeyT = TypeVar("KeyT", bound=Hashable)
ValueT = TypeVar("ValueT")

logger = get_logger(__name__)


class AssetCache(Generic[KeyT, ValueT]):
    """Cache assets with a bounded least-recently-used eviction policy."""

    def __init__(self, max_entries: int, *, name: str) -> None:
        if max_entries < 0:
            raise ValueError("max_entries must be >= 0")
        self._max_entries = max_entries
        self._name = name
        self._entries: OrderedDict[KeyT, ValueT] = OrderedDict()

    def get(self, key: KeyT) -> ValueT | None:
        if self._max_entries == 0:
            return None
        value = self._entries.get(key)
        if value is None:
            return None
        self._entries.move_to_end(key)
        return value

    def set(self, key: KeyT, value: ValueT) -> None:
        if self._max_entries == 0:
            return
        self._entries[key] = value
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            evicted_key, _ = self._entries.popitem(last=False)
            logger.debug("AssetCache(%s) evicted %s", self._name, evicted_key)
