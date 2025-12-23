"""Configuration primitives for :class:`PeripheralManager`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

from heart.peripheral.core import Peripheral

DetectorFactory = Callable[[], Iterable[Peripheral[Any]]]


@dataclass(frozen=True)
class PeripheralConfiguration:
    """Declarative description of a peripheral detection plan."""

    detectors: Sequence[DetectorFactory]

    def __post_init__(self) -> None:
        object.__setattr__(self, "detectors", tuple(self.detectors))
