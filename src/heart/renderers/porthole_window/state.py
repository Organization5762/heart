from dataclasses import dataclass


@dataclass(frozen=True)
class PortholeWindowState:
    elapsed_seconds: float = 0.0

    def advance(self, delta_seconds: float) -> "PortholeWindowState":
        return PortholeWindowState(elapsed_seconds=self.elapsed_seconds + delta_seconds)
