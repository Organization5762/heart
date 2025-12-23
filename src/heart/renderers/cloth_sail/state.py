from dataclasses import dataclass


@dataclass(frozen=True)
class ClothSailState:
    elapsed_seconds: float = 0.0
