from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AvatarBpmRendererState:
    sensor_id: str | None
    bpm: int | None
    avatar_name: str | None

    @classmethod
    def initial(cls) -> "AvatarBpmRendererState":
        return cls(sensor_id=None, bpm=None, avatar_name=None)
