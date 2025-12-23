from __future__ import annotations

from dataclasses import dataclass

from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class SlideTransitionState:
    peripheral_manager: PeripheralManager
    x_offset: int = 0
    target_offset: int | None = None
    sliding: bool = True
    screen_w: int = 0
