from dataclasses import dataclass


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    duration: int | None = None
