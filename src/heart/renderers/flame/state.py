from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlameState:
    time_seconds: float
    dt_seconds: float
