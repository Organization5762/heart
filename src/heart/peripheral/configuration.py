"""Configuration primitives for :class:`PeripheralManager`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from heart.peripheral.core import Peripheral
from heart.peripheral.core.event_bus import VirtualPeripheralDefinition

DetectorFactory = Callable[[], Iterable[Peripheral]]


@dataclass(frozen=True)
class PeripheralConfiguration:
    """Declarative description of a peripheral detection plan."""

    detectors: Sequence[DetectorFactory]
    virtual_peripherals: Sequence[VirtualPeripheralDefinition] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "detectors", tuple(self.detectors))
        object.__setattr__(self, "virtual_peripherals", tuple(self.virtual_peripherals))
