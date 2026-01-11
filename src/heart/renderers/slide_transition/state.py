from __future__ import annotations

from dataclasses import dataclass

from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class SlideTransitionState:
    peripheral_manager: PeripheralManager
    fraction_offset: float = 0.0
    sliding: bool = True
