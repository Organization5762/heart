from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BallPosition:
    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class BallVelocity:
    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class ChildBall:
    position: BallPosition
    velocity: BallVelocity
    age_s: float
    lifetime_s: float
    radius_scale: float


@dataclass(frozen=True, slots=True)
class BouncingBallState:
    position: BallPosition
    velocity: BallVelocity
    last_time_s: float
    force: BallVelocity = BallVelocity(x=0.0, y=0.0, z=0.0)
    trail: tuple[BallPosition, ...] = ()
    child_balls: tuple[ChildBall, ...] = ()
