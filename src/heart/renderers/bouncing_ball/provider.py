from __future__ import annotations

import math
from dataclasses import replace

from manyfold import StreamNode

from heart.peripheral.core.input.frame import FrameTick
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.sensor import Acceleration
from heart.renderers.bouncing_ball.physics import (DEFAULT_BALL_POSITION,
                                                   DEFAULT_BALL_SPEED,
                                                   DEFAULT_MAX_STEP_SECONDS,
                                                   advance_bouncing_ball_state)
from heart.renderers.bouncing_ball.state import BallVelocity, BouncingBallState

ACCELERATION_FORCE_GAIN = 0.16
ACCELERATION_BASELINE_ADAPT_PER_SECOND = 1.4
FORCE_DECAY_SECONDS = 0.65
VELOCITY_DAMPING_PER_SECOND = 0.04
MAX_BALL_SPEED = 1.6


class BouncingBallStateProvider(ObservableProvider[BouncingBallState]):
    """Drive bouncing-ball physics from active accelerometer input."""

    def __init__(self) -> None:
        self._baseline: Acceleration | None = None

    def observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> StreamNode[BouncingBallState]:
        initial = BouncingBallState(
            position=DEFAULT_BALL_POSITION,
            velocity=DEFAULT_BALL_SPEED,
            last_time_s=0.0,
        )
        accelerations = peripheral_manager.input_io.active_acceleration().start_with(
            None
        )
        frame_ticks = peripheral_manager.input_io.frame_tick_stream()
        return (
            frame_ticks.with_latest_from(accelerations)
            .scan(
                lambda state, latest: self._advance_state(
                    state=state,
                    frame_tick=latest[0],
                    acceleration=latest[1],
                ),
                seed=initial,
            )
            .start_with(initial)

        )

    def _advance_state(
        self,
        *,
        state: BouncingBallState,
        frame_tick: FrameTick,
        acceleration: Acceleration | None,
    ) -> BouncingBallState:
        dt = min(max(float(frame_tick.delta_s), 0.0), DEFAULT_MAX_STEP_SECONDS)
        force = self._force_with_acceleration(
            state=state,
            acceleration=acceleration,
            dt=dt,
        )
        velocity = self._velocity_with_force(state=state, force=force, dt=dt)
        physics_state = replace(state, velocity=velocity, force=force)
        return advance_bouncing_ball_state(
            physics_state,
            dt=dt,
            now_s=frame_tick.monotonic_s,
        )

    def _force_with_acceleration(
        self,
        *,
        state: BouncingBallState,
        acceleration: Acceleration | None,
        dt: float,
    ) -> BallVelocity:
        decay = math.exp(-dt / FORCE_DECAY_SECONDS) if dt > 0.0 else 1.0
        fx = state.force.x * decay
        fy = state.force.y * decay
        fz = state.force.z * decay
        if acceleration is None:
            return replace(state.force, x=fx, y=fy, z=fz)

        baseline = self._baseline
        if baseline is None:
            self._baseline = acceleration
            return replace(state.force, x=fx, y=fy, z=fz)

        fx += (acceleration.x - baseline.x) * ACCELERATION_FORCE_GAIN
        fy += (acceleration.y - baseline.y) * ACCELERATION_FORCE_GAIN
        fz += (acceleration.z - baseline.z) * ACCELERATION_FORCE_GAIN

        baseline_alpha = min(1.0, ACCELERATION_BASELINE_ADAPT_PER_SECOND * dt)
        self._baseline = Acceleration(
            x=baseline.x + ((acceleration.x - baseline.x) * baseline_alpha),
            y=baseline.y + ((acceleration.y - baseline.y) * baseline_alpha),
            z=baseline.z + ((acceleration.z - baseline.z) * baseline_alpha),
        )
        return replace(state.force, x=fx, y=fy, z=fz)

    def _velocity_with_force(
        self,
        *,
        state: BouncingBallState,
        force: BallVelocity,
        dt: float,
    ) -> BallVelocity:
        damping = math.exp(-VELOCITY_DAMPING_PER_SECOND * dt) if dt > 0.0 else 1.0
        vx = (state.velocity.x * damping) + (force.x * dt)
        vy = (state.velocity.y * damping) + (force.y * dt)
        vz = (state.velocity.z * damping) + (force.z * dt)
        speed = max((vx * vx + vy * vy + vz * vz) ** 0.5, 1e-9)
        if speed > MAX_BALL_SPEED:
            scale = MAX_BALL_SPEED / speed
            vx *= scale
            vy *= scale
            vz *= scale
        return replace(state.velocity, x=vx, y=vy, z=vz)
