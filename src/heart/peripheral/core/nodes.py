from __future__ import annotations

from typing import TypeVar

from manyfold import EmptyNode, StreamNode

T = TypeVar("T")


def empty_node() -> StreamNode[T]:
    """Return a Manyfold node stream that intentionally emits no values."""
    return EmptyNode()
