from __future__ import annotations

import random
from typing import Generic, TypeVar

from heart.peripheral.core.providers import ObservableProvider

StateT = TypeVar("StateT")


class RngStateProvider(ObservableProvider[StateT], Generic[StateT]):
    """Base provider that manages a shared random number generator."""

    def __init__(self, *, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()

    @property
    def rng(self) -> random.Random:
        return self._rng
