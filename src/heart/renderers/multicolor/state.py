from dataclasses import dataclass


@dataclass(frozen=True)
class MulticolorState:
    elapsed_seconds: float = 0.0
