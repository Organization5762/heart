from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MulticolorState:
    elapsed_seconds: float = 0.0

    def advance(self, dt_seconds: float) -> "MulticolorState":
        return MulticolorState(elapsed_seconds=self.elapsed_seconds + dt_seconds)
