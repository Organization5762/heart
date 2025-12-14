from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClothSailState:
    elapsed_seconds: float = 0.0

    def advance(self, dt_seconds: float) -> "ClothSailState":
        return ClothSailState(elapsed_seconds=self.elapsed_seconds + dt_seconds)
