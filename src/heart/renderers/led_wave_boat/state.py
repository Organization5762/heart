from dataclasses import dataclass

from heart.peripheral.sensor import Acceleration


@dataclass
class SprayParticle:
    x: float
    y: float
    vx: float
    vy: float
    life: float


@dataclass
class LedWaveBoatFrameInput:
    width: int
    height: int
    dt: float
    acceleration: Acceleration | None


@dataclass
class LedWaveBoatState:
    phase: float
    chop_phase: float
    boat_x: float
    boat_y: float
    last_clearance: float
    spray_cooldown: float
    particles: list[SprayParticle]
    heights: list[float]
    sway: float
