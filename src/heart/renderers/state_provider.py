from __future__ import annotations

from typing import Generic, TypeVar

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.providers import ObservableProvider

StateT = TypeVar("StateT")


class ImmutableStateProvider(ObservableProvider[StateT], Generic[StateT]):
    """Emit a single immutable state snapshot without any updates."""

    def __init__(self, state: StateT) -> None:
        self._state = state

    def observable(self) -> reactivex.Observable[StateT]:
        return reactivex.just(self._state).pipe(ops.share())
