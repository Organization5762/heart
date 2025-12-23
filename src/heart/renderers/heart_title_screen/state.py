from dataclasses import dataclass


@dataclass(frozen=True)
class HeartTitleScreenState:
    heart_up: bool = True
    elapsed_ms: float = 0.0
