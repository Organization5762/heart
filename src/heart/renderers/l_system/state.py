from dataclasses import dataclass


@dataclass(frozen=True)
class LSystemState:
    grammar: str = "X"
    time_since_last_update_ms: float = 0.0
