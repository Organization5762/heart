from dataclasses import dataclass


@dataclass(frozen=True)
class WaterTitleScreenState:
    wave_offset: float = 0.0
