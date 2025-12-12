from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WaterTitleScreenState:
    wave_offset: float

    @classmethod
    def initial(cls) -> "WaterTitleScreenState":
        return cls(wave_offset=0.0)

    def advance(self, wave_speed: float, dt_seconds: float) -> "WaterTitleScreenState":
        return WaterTitleScreenState(
            wave_offset=self.wave_offset + wave_speed * dt_seconds * 60.0
        )
