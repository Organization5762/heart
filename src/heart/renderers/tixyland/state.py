from dataclasses import dataclass


@dataclass(frozen=True)
class TixylandState:
    """Timing state for the Tixy-inspired shader."""

    time_seconds: float = 0.0
