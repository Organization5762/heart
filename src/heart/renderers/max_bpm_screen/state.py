from dataclasses import dataclass


@dataclass(frozen=True)
class AvatarBpmRendererState:
    sensor_id: str | None
    bpm: int | None
    avatar_name: str | None
