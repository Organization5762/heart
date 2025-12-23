from dataclasses import dataclass


@dataclass(frozen=True)
class CombinedBpmScreenState:
    elapsed_time_ms: float = 0.0
    showing_metadata: bool = True
