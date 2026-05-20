from dataclasses import dataclass

DEFAULT_TIXYLAND_HUE_DEGREES = 190.0


@dataclass(frozen=True)
class TixylandState:
    """Timing state for the Tixy-inspired shader."""

    time_seconds: float = 0.0
    speed_scale: float = 1.0
    hue_degrees: float = DEFAULT_TIXYLAND_HUE_DEGREES
    seed: int = 0
