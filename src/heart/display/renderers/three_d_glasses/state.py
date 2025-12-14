from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThreeDGlassesState:
    current_index: int = 0
    elapsed_ms: float = 0.0
