from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CombinedBpmScreenState:
    elapsed_time_ms: float = 0.0
    showing_metadata: bool = True

    @classmethod
    def initial(cls) -> "CombinedBpmScreenState":
        return cls()
