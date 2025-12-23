from dataclasses import dataclass


@dataclass(frozen=True)
class PortholeWindowState:
    elapsed_seconds: float = 0.0
