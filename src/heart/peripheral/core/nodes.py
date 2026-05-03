from __future__ import annotations

from typing import TypeVar, cast

from heart.utilities import reactive

T = TypeVar("T")


def empty_node() -> reactive.Observable[T]:
    """Return a Manyfold node stream that intentionally emits no values."""
    return cast(reactive.Observable[T], reactive.empty())
