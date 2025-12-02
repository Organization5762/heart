"""Renderer that turns accelerometer data into animated LED waves with a boat."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class _SprayParticle:
    x: float
    y: float
    vx: float
    vy: float
    life: float


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


class LedWaveBoat(BaseRenderer):
    """Render sinusoidal water motion driven by accelerometer input."""

    _HULL_DEPTH = 1.0
    _BOAT_HALF_WIDTH = 2.0

    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED

        self._phase = 0.0
        self._chop_phase = 0.0
        self._boat_x = 0.0
        self._boat_y = 0.0
        self._last_clearance = 4.0
        self._spray_cooldown = 0.0
        self._particles: list[_SprayParticle] = []
        self._rng = random.Random()

    # ------------------------------------------------------------------
    def _sample_acceleration(
        self, peripheral_manager: PeripheralManager
    ) -> tuple[float, float, float]:
        try:
            accel = peripheral_manager.get_accelerometer().get_acceleration()
        except ValueError:
            accel = None
        if accel is None:
            return (0.0, 0.0, 9.81)
        return (accel.x, accel.y, accel.z)

    def _generate_wave(
        self,
        width: int,
        base_line: float,
        amplitude: float,
        phase_primary: float,
        phase_secondary: float,
        sway: float,
    ) -> list[float]:
        # Precompute wave number factors once for efficiency.
        k_primary = 2.0 * math.pi / max(width, 1)
        k_secondary = 2.0 * math.pi * 2.7 / max(width, 1)

        heights: list[float] = []
        for x in range(width):
            wave = math.sin(k_primary * (x + sway) + phase_primary)
            small_wave = 0.45 * math.sin(k_secondary * x + phase_secondary)
            chop = 0.15 * math.sin(3.5 * k_primary * x - phase_primary * 1.6)
            heights.append(base_line + amplitude * (wave + small_wave + chop))
        return heights

    def _update_particles(self, dt: float, height_limit: int) -> None:
        gravity = 88.0
        damp = 0.92

        next_particles: list[_SprayParticle] = []
        for particle in self._particles:
            particle.life -= dt
            if particle.life <= 0:
                continue

            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vy += gravity * dt
            particle.vx *= damp

            if particle.y >= height_limit:
                continue
            next_particles.append(particle)

        self._particles = next_particles

    def _spawn_spray(self, origin_x: float, origin_y: float) -> None:
        for _ in range(6):
            speed = self._rng.uniform(32.0, 60.0)
            angle = self._rng.uniform(-math.pi / 3.2, math.pi / 3.2)
            vx = speed * math.cos(angle) * 0.5
            vy = -abs(speed * math.sin(angle)) - self._rng.uniform(10.0, 18.0)
            life = self._rng.uniform(0.25, 0.45)
            self._particles.append(
                _SprayParticle(x=origin_x, y=origin_y, vx=vx, vy=vy, life=life)
            )

    def _draw_water_column(
        self,
        screen: Surface,
        column: int,
        crest_y: int,
        screen_height: int,
        crest_color: tuple[int, int, int],
        body_color: tuple[int, int, int],
    ) -> None:
        pygame.draw.line(screen, body_color, (column, crest_y), (column, screen_height - 1))
        screen.set_at((column, crest_y), crest_color)

    def _draw_boat(self, screen: Surface, x: float, y: float, sway: float) -> None:
        # Offset the sail by sway to hint at boat roll.
        sail_offset = int(round(sway))
        px = int(round(x))
        py = int(round(y))

        hull_color = (120, 78, 48)
        deck_color = (170, 120, 90)
        mast_color = (90, 66, 42)
        sail_color = (235, 240, 255)
        sail_shadow = (180, 200, 255)

        sprite = (
            (-2, 1, hull_color),
            (-1, 1, hull_color),
            (0, 1, hull_color),
            (1, 1, hull_color),
            (-1, 0, deck_color),
            (0, 0, deck_color),
            (0, -1, mast_color),
            (0, -2, mast_color),
            (1, -2 + sail_offset, sail_color),
            (2, -2 + sail_offset, sail_color),
            (1, -3 + sail_offset, sail_shadow),
        )

        width, height = screen.get_size()
        for dx, dy, color in sprite:
            sx = px + dx
            sy = py + dy
            if 0 <= sx < width and 0 <= sy < height:
                screen.set_at((sx, sy), color)

    def _draw_particles(self, screen: Surface) -> None:
        spray_color = (190, 220, 255)
        width, height = screen.get_size()
        for particle in self._particles:
            sx = int(round(particle.x))
            sy = int(round(particle.y))
            if 0 <= sx < width and 0 <= sy < height:
                screen.set_at((sx, sy), spray_color)

    # ------------------------------------------------------------------
    def process(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        if width == 0 or height == 0:
            return

        dt_ms = clock.get_time()
        dt = max(dt_ms / 1000.0, 1.0 / 120.0)

        ax, ay, az = self._sample_acceleration(peripheral_manager)
        horizontal_mag = math.hypot(ax, ay)
        norm_ax = _clamp(ax / 9.81, -1.0, 1.0)
        norm_ay = _clamp(ay / 9.81, -1.0, 1.0)
        norm_az = _clamp(az / 9.81, -1.0, 1.0)

        base_line = height * (0.62 - 0.08 * norm_az)
        amplitude = 2.2 + min(height * 0.22, horizontal_mag * 0.55)

        speed_primary = 1.3 + horizontal_mag * 0.15
        speed_secondary = 0.9 + abs(norm_ay) * 0.35
        sway = norm_ax * 8.0

        self._phase = (self._phase + dt * speed_primary) % (2.0 * math.pi)
        self._chop_phase = (self._chop_phase + dt * speed_secondary) % (2.0 * math.pi)

        heights = self._generate_wave(
            width=width,
            base_line=base_line,
            amplitude=amplitude,
            phase_primary=self._phase,
            phase_secondary=self._chop_phase,
            sway=sway,
        )

        target_x = width / 2.0 + norm_ax * (width * 0.28)
        if self._boat_x == 0.0:
            self._boat_x = target_x
        else:
            self._boat_x += (target_x - self._boat_x) * min(1.0, dt * 3.0)

        boat_column = int(_clamp(round(self._boat_x), 0, width - 1))
        wave_height = heights[boat_column]
        target_boat_y = wave_height - 2.0
        if self._boat_y == 0.0:
            self._boat_y = target_boat_y
        else:
            self._boat_y += (target_boat_y - self._boat_y) * min(1.0, dt * 4.5)

        clearance = (self._boat_y + self._HULL_DEPTH) - wave_height
        self._spray_cooldown = max(0.0, self._spray_cooldown - dt)
        if clearance <= -0.2 and self._last_clearance > -0.05 and self._spray_cooldown <= 0.0:
            self._spawn_spray(origin_x=self._boat_x, origin_y=wave_height - 1.0)
            self._spray_cooldown = 0.18
        self._last_clearance = clearance

        self._update_particles(dt, height)

        window.fill((5, 8, 20))

        foam_color = (185, 220, 255)
        water_color = (20, 80, 150)
        deep_color = (10, 30, 70)

        for x, crest in enumerate(heights):
            crest_px = int(_clamp(round(crest), 0, height - 1))
            slope = heights[x] - heights[x - 1 if x > 0 else -1]
            crest_mix = _clamp(abs(slope) * 0.6, 0.0, 1.0)
            crest_color = (
                int(foam_color[0] * crest_mix + water_color[0] * (1 - crest_mix)),
                int(foam_color[1] * crest_mix + water_color[1] * (1 - crest_mix)),
                int(foam_color[2] * crest_mix + water_color[2] * (1 - crest_mix)),
            )
            if crest_px < height - 1:
                self._draw_water_column(
                    window,
                    column=x,
                    crest_y=crest_px,
                    screen_height=height,
                    crest_color=crest_color,
                    body_color=deep_color,
                )
            else:
                window.set_at((x, crest_px), crest_color)

        self._draw_particles(window)
        self._draw_boat(window, self._boat_x, self._boat_y, sway)