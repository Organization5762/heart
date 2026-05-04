from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from manyfold import MergeNode, StreamNode

T = TypeVar("T")
U = TypeVar("U")


def map_stream(source: StreamNode[T], mapper: Callable[[T], U]) -> StreamNode[U]:
    return source.map(mapper)


def merge_streams(*streams: StreamNode[T]) -> StreamNode[T]:
    return MergeNode.merge(*streams)


def threshold_direction(value: float, threshold: float) -> int:
    if value >= threshold:
        return 1
    if value <= -threshold:
        return -1
    return 0
