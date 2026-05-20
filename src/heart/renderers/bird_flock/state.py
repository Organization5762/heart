from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bird:
    x: float
    y: float
    vx: float
    vy: float
    phase: float


@dataclass(frozen=True)
class BirdFlockState:
    birds: tuple[Bird, ...]
    last_time_s: float
    hue_degrees: float = 205.0
