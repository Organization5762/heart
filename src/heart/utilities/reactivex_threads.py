from __future__ import annotations

from collections.abc import Callable
from typing import Any

import reactivex


def pipe_in_background(
    source: reactivex.Observable[Any],
    *operators: Callable[[reactivex.Observable[Any]], reactivex.Observable[Any]],
) -> reactivex.Observable[Any]:
    return source.pipe(*operators)
