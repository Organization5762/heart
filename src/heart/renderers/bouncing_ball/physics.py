from __future__ import annotations

from dataclasses import replace

from heart.renderers.bouncing_ball.state import (BallPosition, BallVelocity,
                                                 BouncingBallState, ChildBall)

WORLD_LIMIT = 1.0
Y_FLOOR = -0.78
Y_CEILING = 0.78
DEFAULT_TRAIL_LENGTH = 10
DEFAULT_MAX_STEP_SECONDS = 1.0 / 20.0
DEFAULT_BALL_SPEED = BallVelocity(x=0.68, y=0.52, z=0.9)
DEFAULT_BALL_POSITION = BallPosition(x=-0.24, y=0.14, z=-0.32)
IMPACT_SPAWN_SPEED_THRESHOLD = 1.05
CHILD_BALL_LIFETIME_SECONDS = 1.15
MAX_CHILD_BALLS = 18


def advance_bouncing_ball_state(
    state: BouncingBallState,
    *,
    dt: float,
    now_s: float,
) -> BouncingBallState:
    child_balls = _advance_child_balls(state.child_balls, dt=dt)
    next_position = BallPosition(
        x=state.position.x + state.velocity.x * dt,
        y=state.position.y + state.velocity.y * dt,
        z=state.position.z + state.velocity.z * dt,
    )
    next_velocity = state.velocity
    impact_axis = ""
    impact_speed = 0.0

    next_position, next_velocity, speed = bounce_axis(
        position=next_position,
        velocity=next_velocity,
        axis="x",
        low=-WORLD_LIMIT,
        high=WORLD_LIMIT,
    )
    if speed > impact_speed:
        impact_axis = "x"
        impact_speed = speed
    next_position, next_velocity, speed = bounce_axis(
        position=next_position,
        velocity=next_velocity,
        axis="z",
        low=-WORLD_LIMIT,
        high=WORLD_LIMIT,
    )
    if speed > impact_speed:
        impact_axis = "z"
        impact_speed = speed
    next_position, next_velocity, speed = bounce_axis(
        position=next_position,
        velocity=next_velocity,
        axis="y",
        low=Y_FLOOR,
        high=Y_CEILING,
    )
    if speed > impact_speed:
        impact_axis = "y"
        impact_speed = speed

    if impact_speed >= IMPACT_SPAWN_SPEED_THRESHOLD:
        child_balls = (
            *spawn_child_balls(
                position=next_position,
                velocity=next_velocity,
                impact_axis=impact_axis,
                impact_speed=impact_speed,
            ),
            *child_balls,
        )[:MAX_CHILD_BALLS]

    return replace(
        state,
        position=next_position,
        velocity=next_velocity,
        last_time_s=now_s,
        trail=(state.position, *state.trail[: DEFAULT_TRAIL_LENGTH - 1]),
        child_balls=child_balls,
    )


def bounce_axis(
    *,
    position: BallPosition,
    velocity: BallVelocity,
    axis: str,
    low: float,
    high: float,
) -> tuple[BallPosition, BallVelocity, float]:
    value = getattr(position, axis)
    speed = getattr(velocity, axis)
    impact_speed = 0.0
    if value < low:
        value = low + (low - value)
        impact_speed = abs(speed)
        speed = abs(speed)
    elif value > high:
        value = high - (value - high)
        impact_speed = abs(speed)
        speed = -abs(speed)
    return (
        replace(position, **{axis: value}),
        replace(velocity, **{axis: speed}),
        impact_speed,
    )


def spawn_child_balls(
    *,
    position: BallPosition,
    velocity: BallVelocity,
    impact_axis: str,
    impact_speed: float,
) -> tuple[ChildBall, ...]:
    if not impact_axis:
        return ()
    base_speed = max(0.25, min(1.2, impact_speed * 0.55))
    axis_push = {
        "x": BallVelocity(x=-_sign(velocity.x) * base_speed, y=0.0, z=0.0),
        "y": BallVelocity(x=0.0, y=-_sign(velocity.y) * base_speed, z=0.0),
        "z": BallVelocity(x=0.0, y=0.0, z=-_sign(velocity.z) * base_speed),
    }[impact_axis]
    offsets = (-0.42, 0.0, 0.42)
    return tuple(
        ChildBall(
            position=position,
            velocity=BallVelocity(
                x=(velocity.x * 0.22)
                + axis_push.x
                + _tangent_component(impact_axis, offset, "x"),
                y=(velocity.y * 0.22)
                + axis_push.y
                + _tangent_component(impact_axis, offset, "y"),
                z=(velocity.z * 0.22)
                + axis_push.z
                + _tangent_component(impact_axis, offset, "z"),
            ),
            age_s=0.0,
            lifetime_s=CHILD_BALL_LIFETIME_SECONDS,
            radius_scale=0.28 + (index * 0.06),
        )
        for index, offset in enumerate(offsets)
    )


def _advance_child_balls(
    child_balls: tuple[ChildBall, ...],
    *,
    dt: float,
) -> tuple[ChildBall, ...]:
    result: list[ChildBall] = []
    for child in child_balls:
        age_s = child.age_s + dt
        if age_s >= child.lifetime_s:
            continue
        position = BallPosition(
            x=child.position.x + child.velocity.x * dt,
            y=child.position.y + child.velocity.y * dt,
            z=child.position.z + child.velocity.z * dt,
        )
        velocity = child.velocity
        position, velocity, _ = bounce_axis(
            position=position,
            velocity=velocity,
            axis="x",
            low=-WORLD_LIMIT,
            high=WORLD_LIMIT,
        )
        position, velocity, _ = bounce_axis(
            position=position,
            velocity=velocity,
            axis="z",
            low=-WORLD_LIMIT,
            high=WORLD_LIMIT,
        )
        position, velocity, _ = bounce_axis(
            position=position,
            velocity=velocity,
            axis="y",
            low=Y_FLOOR,
            high=Y_CEILING,
        )
        result.append(replace(child, position=position, velocity=velocity, age_s=age_s))
    return tuple(result)


def _sign(value: float) -> float:
    return 1.0 if value >= 0.0 else -1.0


def _tangent_component(impact_axis: str, offset: float, target_axis: str) -> float:
    if target_axis == impact_axis:
        return 0.0
    if impact_axis == "x":
        return offset if target_axis == "z" else offset * 0.45
    if impact_axis == "z":
        return offset if target_axis == "x" else offset * 0.45
    return offset if target_axis == "x" else offset * -0.35
