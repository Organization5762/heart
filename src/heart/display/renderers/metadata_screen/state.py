from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

DEFAULT_HEART_COLORS = [
    "bluer",
    "blue",
    "green",
    "orange",
    "pink",
    "purple",
    "teal",
    "yellow",
]


@dataclass(frozen=True)
class HeartAnimationState:
    up: bool
    color_index: int
    last_update_ms: float


@dataclass(frozen=True)
class MetadataScreenState:
    heart_states: Dict[str, HeartAnimationState] = field(default_factory=dict)
    time_since_last_update_ms: float = 0.0

    @classmethod
    def initial(cls) -> "MetadataScreenState":
        return cls()
