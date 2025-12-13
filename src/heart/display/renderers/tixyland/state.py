from dataclasses import dataclass


@dataclass(frozen=True)
class TixylandState:
    """Timing state for the Tixy-inspired shader."""

    time_seconds: float = 0.0

    def advance(self, delta_seconds: float) -> "TixylandState":
        return TixylandState(time_seconds=self.time_seconds + delta_seconds)
