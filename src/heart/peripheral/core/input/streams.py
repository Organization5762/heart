from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import heart.utilities.reactive as reactive
from heart.utilities.reactive import operators as ops
from heart.utilities.reactive_threads import pipe_in_background

T = TypeVar("T")
U = TypeVar("U")


def map_stream(
    source: reactive.Observable[T],
    mapper: Callable[[T], U],
) -> reactive.Observable[U]:
    return pipe_in_background(source, ops.map(mapper))


def merge_streams(
    *streams: reactive.Observable[T],
) -> reactive.Observable[T]:
    return pipe_in_background(reactive.merge(*streams))


def threshold_direction(value: float, threshold: float) -> int:
    if value >= threshold:
        return 1
    if value <= -threshold:
        return -1
    return 0
