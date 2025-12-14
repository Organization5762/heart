from dataclasses import dataclass


@dataclass(frozen=True)
class ClothSailState:
    start_time: float
    elapsed: float
