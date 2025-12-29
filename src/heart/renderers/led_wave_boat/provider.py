from __future__ import annotations

import math
import random
from random import Random

import reactivex
from pygame.time import Clock
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.providers.acceleration import AllAccelerometersProvider
from heart.peripheral.sensor import Acceleration
from heart.renderers.led_wave_boat.state import (LedWaveBoatFrameInput,
                                                 LedWaveBoatState,
                                                 SprayParticle)
from heart.utilities.reactivex_threads import pipe_in_background

HULL_DEPTH = 1.0


class LedWaveBoatStateProvider(ObservableProvider[LedWaveBoatState]):
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        accelerometers: AllAccelerometersProvider,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._accelerometers = accelerometers
        self._rng = random.Random()

    def observable(self) -> reactivex.Observable[LedWaveBoatState]:
        window_sizes = pipe_in_background(
            self._peripheral_manager.window,
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: window.get_size()),
            ops.distinct_until_changed(),
            ops.share(),
        )
        clocks = pipe_in_background(
            self._peripheral_manager.clock,
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )
        accelerations = pipe_in_background(
            self._accelerometers.observable(),
            ops.start_with(None),
            ops.share(),
        )

        frame_inputs = pipe_in_background(
            self._peripheral_manager.game_tick,
            ops.with_latest_from(window_sizes, clocks, accelerations),
            ops.map(self._to_frame_input),
        )

        initial_state = self._initial_state()

        return pipe_in_background(
            frame_inputs,
            ops.scan(
                lambda state, frame: self._advance_state(state=state, frame=frame),
                seed=initial_state,
            ),
            ops.start_with(initial_state),
            ops.share(),
        )

    @staticmethod
    def _to_frame_input(
        latest: tuple[
            object | None,
            tuple[int, int],
            Clock,
            Acceleration | None,
        ]
    ) -> LedWaveBoatFrameInput:
        _, window_size, clock, acceleration = latest
        width, height = window_size
        dt = max(clock.get_time() / 1000.0, 1.0 / 120.0)

        return LedWaveBoatFrameInput(
            width=width,
            height=height,
            dt=dt,
            acceleration=acceleration,
        )

    @staticmethod
    def _initial_state() -> LedWaveBoatState:
        return LedWaveBoatState(
            phase=0.0,
            chop_phase=0.0,
            boat_x=0.0,
            boat_y=0.0,
            last_clearance=4.0,
            spray_cooldown=0.0,
            particles=[],
            heights=[0.0],
            sway=0.0,
        )

    def _advance_state(
        self, *, state: LedWaveBoatState, frame: LedWaveBoatFrameInput
    ) -> LedWaveBoatState:
        if frame.width <= 0 or frame.height <= 0:
            return state

        ax, ay, az = self._normalize_acceleration(frame.acceleration)
        horizontal_mag = math.hypot(ax, ay)
        norm_ax = self._clamp(ax / 9.81, -1.0, 1.0)
        norm_ay = self._clamp(ay / 9.81, -1.0, 1.0)
        norm_az = self._clamp(az / 9.81, -1.0, 1.0)

        base_line = frame.height * (0.62 - 0.08 * norm_az)
        amplitude = 2.2 + min(frame.height * 0.22, horizontal_mag * 0.55)

        speed_primary = 1.3 + horizontal_mag * 0.15
        speed_secondary = 0.9 + abs(norm_ay) * 0.35
        sway = norm_ax * 8.0

        phase = (state.phase + frame.dt * speed_primary) % (2.0 * math.pi)
        chop_phase = (state.chop_phase + frame.dt * speed_secondary) % (2.0 * math.pi)

        heights = self._generate_wave(
            width=frame.width,
            base_line=base_line,
            amplitude=amplitude,
            phase_primary=phase,
            phase_secondary=chop_phase,
            sway=sway,
        )

        target_x = frame.width / 2.0 + norm_ax * (frame.width * 0.28)
        boat_x = self._lerp_value(state.boat_x, target_x, frame.dt * 3.0)

        boat_column = int(self._clamp(round(boat_x), 0, frame.width - 1))
        wave_height = heights[boat_column]
        target_boat_y = wave_height - 2.0
        boat_y = self._lerp_value(state.boat_y, target_boat_y, frame.dt * 4.5)

        clearance = (boat_y + HULL_DEPTH) - wave_height
        spray_cooldown = max(0.0, state.spray_cooldown - frame.dt)
        particles = self._update_particles(state.particles, frame.dt, frame.height)
        if (
            clearance <= -0.2
            and state.last_clearance > -0.05
            and spray_cooldown <= 0.0
        ):
            particles.extend(
                self._spawn_spray(
                    self._rng, origin_x=boat_x, origin_y=wave_height - 1.0
                )
            )
            spray_cooldown = 0.18

        return LedWaveBoatState(
            phase=phase,
            chop_phase=chop_phase,
            boat_x=boat_x,
            boat_y=boat_y,
            last_clearance=clearance,
            spray_cooldown=spray_cooldown,
            particles=particles,
            heights=heights,
            sway=sway,
        )

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    @staticmethod
    def _normalize_acceleration(
        accel: Acceleration | None,
    ) -> tuple[float, float, float]:
        if accel is None:
            return (0.0, 0.0, 9.81)
        return (accel.x, accel.y, accel.z)

    @classmethod
    def _lerp_value(cls, previous: float, target: float, factor: float) -> float:
        factor = cls._clamp(factor, 0.0, 1.0)
        if previous == 0.0:
            return target
        return previous + (target - previous) * factor

    @staticmethod
    def _generate_wave(
        *,
        width: int,
        base_line: float,
        amplitude: float,
        phase_primary: float,
        phase_secondary: float,
        sway: float,
    ) -> list[float]:
        k_primary = 2.0 * math.pi / max(width, 1)
        k_secondary = 2.0 * math.pi * 2.7 / max(width, 1)

        heights: list[float] = []
        for x in range(width):
            wave = math.sin(k_primary * (x + sway) + phase_primary)
            small_wave = 0.45 * math.sin(k_secondary * x + phase_secondary)
            chop = 0.15 * math.sin(3.5 * k_primary * x - phase_primary * 1.6)
            heights.append(base_line + amplitude * (wave + small_wave + chop))
        return heights

    @staticmethod
    def _update_particles(
        particles: list[SprayParticle], dt: float, height_limit: int
    ) -> list[SprayParticle]:
        gravity = 88.0
        damp = 0.92

        next_particles: list[SprayParticle] = []
        for particle in particles:
            life = particle.life - dt
            if life <= 0:
                continue

            x = particle.x + particle.vx * dt
            y = particle.y + particle.vy * dt
            vy = particle.vy + gravity * dt
            vx = particle.vx * damp

            if y >= height_limit:
                continue
            next_particles.append(
                SprayParticle(x=x, y=y, vx=vx, vy=vy, life=life)
            )

        return next_particles

    @staticmethod
    def _spawn_spray(
        rng: Random, *, origin_x: float, origin_y: float, bursts: int = 6
    ) -> list[SprayParticle]:
        particles: list[SprayParticle] = []
        for _ in range(bursts):
            speed = rng.uniform(32.0, 60.0)
            angle = rng.uniform(-math.pi / 3.2, math.pi / 3.2)
            vx = speed * math.cos(angle) * 0.5
            vy = -abs(speed * math.sin(angle)) - rng.uniform(10.0, 18.0)
            life = rng.uniform(0.25, 0.45)
            particles.append(
                SprayParticle(x=origin_x, y=origin_y, vx=vx, vy=vy, life=life)
            )
        return particles
