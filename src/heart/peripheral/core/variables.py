from __future__ import annotations

from typing import TypeAlias, TypeVar

from manyfold.graph import ObservableLike

T = TypeVar("T")

Variable: TypeAlias = ObservableLike[T]
