from __future__ import annotations

import math
import random
import time
from colorsys import hsv_to_rgb

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, GamepadSnapshotEvent)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.bird_flock.state import Bird, BirdFlockState
from heart.runtime.display_context import DisplayContext

DEFAULT_BIRD_COUNT = 24
MIN_BIRD_COUNT = 5
MAX_BIRD_COUNT = 56
BIRD_COUNT_STEP_PER_FRAME = 1
HUE_DEGREES_PER_SECOND = 130.0
MIN_SPEED = 10.0
MAX_SPEED = 32.0
NEIGHBOR_RADIUS = 31.0
SEPARATION_RADIUS = 9.0
ALIGNMENT_WEIGHT = 0.72
COHESION_WEIGHT = 0.18
SEPARATION_WEIGHT = 1.85
CENTER_PULL_WEIGHT = 0.018
SKY_TOP = (3, 8, 23)
SKY_MIDDLE = (16, 31, 58)
SKY_BOTTOM = (56, 50, 78)
BIRD_SHADOW = (62, 92, 126)
WING_HIGHLIGHT = (255, 205, 132)
SEAGULL_WHITE = (245, 248, 246)
SEAGULL_GRAY = (172, 187, 196)
SEAGULL_DARK_TIP = (34, 45, 56)
SEAGULL_BEAK = (255, 190, 76)
MOON_COLOR = (255, 233, 176)
CLOUD_COLOR = (62, 83, 112)


class BirdFlockRenderer(StatefulBaseRenderer[BirdFlockState]):
    """Render a small flock that steers around the full totem display."""

    def __init__(self, *, seed: int = 1701) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._peripheral_manager: PeripheralManager | None = None
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        super().initialize(window, peripheral_manager, orientation)

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> BirdFlockState:
        del peripheral_manager, orientation
        width, height = window.get_size()
        return BirdFlockState(
            birds=tuple(
                _create_bird(self._rng, width=width, height=height)
                for _ in range(DEFAULT_BIRD_COUNT)
            ),
            last_time_s=time.monotonic(),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        now_s = time.monotonic()
        width, height = window.get_size()
        dt = min(max(now_s - self.state.last_time_s, 0.0), 0.06)
        birds = self.state.birds
        hue_degrees = self.state.hue_degrees
        for event in self._sample_gamepads():
            birds = self._apply_count_control(
                birds=birds,
                gamepad=event.snapshot,
                width=width,
                height=height,
            )
            hue_degrees = _controlled_hue(
                hue_degrees=hue_degrees,
                gamepad=event.snapshot,
                dt=dt,
            )
        state = BirdFlockState(
            birds=self._advance_birds(
                birds=birds,
                width=width,
                height=height,
                dt=dt,
            ),
            last_time_s=now_s,
            hue_degrees=hue_degrees,
        )
        self.set_state(state)
        self._draw_sky(window.screen, width=width, height=height)
        self._draw_birds(
            window.screen,
            birds=state.birds,
            now_s=now_s,
            bird_color=_bird_color(hue_degrees),
        )

    def _sample_gamepads(self) -> tuple[GamepadSnapshotEvent, ...]:
        if self._peripheral_manager is None:
            return ()
        return self._peripheral_manager.input_io.controls.gamepads()

    def _apply_count_control(
        self,
        *,
        birds: tuple[Bird, ...],
        gamepad: GamepadSnapshot,
        width: int,
        height: int,
    ) -> tuple[Bird, ...]:
        if not gamepad.connected:
            return birds
        count_delta = 0
        if gamepad.button_held(GamepadButton.ZR):
            count_delta += BIRD_COUNT_STEP_PER_FRAME
        if gamepad.button_held(GamepadButton.ZL):
            count_delta -= BIRD_COUNT_STEP_PER_FRAME
        if count_delta == 0:
            return birds

        target_count = max(
            MIN_BIRD_COUNT,
            min(MAX_BIRD_COUNT, len(birds) + count_delta),
        )
        if target_count < len(birds):
            return birds[:target_count]
        if target_count == len(birds):
            return birds
        return (
            *birds,
            *(
                _create_bird(self._rng, width=width, height=height)
                for _ in range(target_count - len(birds))
            ),
        )

    @classmethod
    def _advance_birds(
        cls,
        *,
        birds: tuple[Bird, ...],
        width: int,
        height: int,
        dt: float,
    ) -> tuple[Bird, ...]:
        next_birds: list[Bird] = []
        center_x = width / 2
        center_y = height / 2
        for bird in birds:
            neighbor_count = 0
            avg_x = 0.0
            avg_y = 0.0
            avg_vx = 0.0
            avg_vy = 0.0
            sep_x = 0.0
            sep_y = 0.0
            for other in birds:
                if other is bird:
                    continue
                dx = _wrapped_delta(other.x - bird.x, width)
                dy = other.y - bird.y
                distance = math.hypot(dx, dy)
                if distance > NEIGHBOR_RADIUS:
                    continue
                neighbor_count += 1
                avg_x += bird.x + dx
                avg_y += other.y
                avg_vx += other.vx
                avg_vy += other.vy
                if 0.001 < distance < SEPARATION_RADIUS:
                    repel = (SEPARATION_RADIUS - distance) / SEPARATION_RADIUS
                    sep_x -= dx / distance * repel
                    sep_y -= dy / distance * repel

            ax = (center_x - bird.x) * CENTER_PULL_WEIGHT
            ay = (center_y - bird.y) * CENTER_PULL_WEIGHT
            if neighbor_count:
                inv_count = 1.0 / neighbor_count
                avg_x *= inv_count
                avg_y *= inv_count
                avg_vx *= inv_count
                avg_vy *= inv_count
                ax += (avg_vx - bird.vx) * ALIGNMENT_WEIGHT
                ay += (avg_vy - bird.vy) * ALIGNMENT_WEIGHT
                ax += _wrapped_delta(avg_x - bird.x, width) * COHESION_WEIGHT
                ay += (avg_y - bird.y) * COHESION_WEIGHT
                ax += sep_x * SEPARATION_WEIGHT * MAX_SPEED
                ay += sep_y * SEPARATION_WEIGHT * MAX_SPEED

            wander = math.sin((bird.phase * 2.7) + bird.x * 0.05) * 8.0
            vx = bird.vx + (ax + wander) * dt
            vy = bird.vy + ay * dt
            vx, vy = _clamp_velocity(vx, vy)
            x = (bird.x + vx * dt) % max(width, 1)
            y = bird.y + vy * dt
            if y < 5:
                y = 5
                vy = abs(vy) * 0.75
            elif y > height - 6:
                y = height - 6
                vy = -abs(vy) * 0.75
            next_birds.append(Bird(x=x, y=y, vx=vx, vy=vy, phase=bird.phase + dt))
        return tuple(next_birds)

    @staticmethod
    def _draw_sky(screen: pygame.Surface, *, width: int, height: int) -> None:
        for y in range(height):
            ratio = y / max(height - 1, 1)
            if ratio < 0.58:
                color = _mix_color(SKY_TOP, SKY_MIDDLE, ratio / 0.58)
            else:
                color = _mix_color(SKY_MIDDLE, SKY_BOTTOM, (ratio - 0.58) / 0.42)
            pygame.draw.line(screen, color, (0, y), (width, y))
        _draw_moon(screen, width=width)
        _draw_cloud_band(
            screen,
            width=width,
            y=max(8, height // 5),
            offset=0,
        )
        _draw_cloud_band(
            screen,
            width=width,
            y=max(12, height // 3),
            offset=29,
        )
        for x in range(0, width, 19):
            y = 6 + ((x * 11) % max(height - 15, 1))
            screen.set_at((x, y), _mix_color((53, 85, 120), MOON_COLOR, 0.2))

    def _draw_birds(
        self,
        screen: pygame.Surface,
        *,
        birds: tuple[Bird, ...],
        now_s: float,
        bird_color: tuple[int, int, int],
    ) -> None:
        for bird in sorted(birds, key=lambda item: item.y):
            depth = bird.y / max(screen.get_height(), 1)
            self._draw_bird(
                screen,
                bird=bird,
                now_s=now_s,
                bird_color=_bird_tint(bird_color, depth=depth, phase=bird.phase),
            )

    def _draw_bird(
        self,
        screen: pygame.Surface,
        *,
        bird: Bird,
        now_s: float,
        bird_color: tuple[int, int, int],
    ) -> None:
        angle = math.atan2(bird.vy, bird.vx)
        speed = math.hypot(bird.vx, bird.vy)
        scale = 3.2 + min(speed / MAX_SPEED, 1.0) * 2.4
        flap = math.sin(now_s * 7.0 + bird.phase * 5.0)
        forward = (math.cos(angle), math.sin(angle))
        normal = (-forward[1], forward[0])
        center = (bird.x, bird.y)
        nose = _offset(center, forward, scale * 1.18)
        tail = _offset(center, forward, -scale * 0.88)
        left_root = _offset(center, normal, scale * 0.32)
        right_root = _offset(center, normal, -scale * 0.32)
        wing_lift = flap * scale * 0.18
        left_tip = _offset(
            _offset(center, normal, scale * 1.85),
            forward,
            -scale * 0.72 + wing_lift,
        )
        right_tip = _offset(
            _offset(center, normal, -scale * 1.85),
            forward,
            -scale * 0.72 + wing_lift,
        )
        left_outer = _offset(left_tip, forward, scale * 0.52)
        right_outer = _offset(right_tip, forward, scale * 0.52)
        beak = _offset(nose, forward, max(1.0, scale * 0.35))
        shadow_offset = (1, 1)
        shadow_points = _translate_points(
            [
                (round(nose[0]), round(nose[1])),
                (round(left_outer[0]), round(left_outer[1])),
                (round(tail[0]), round(tail[1])),
                (round(right_outer[0]), round(right_outer[1])),
            ],
            shadow_offset,
        )
        wing_color = _mix_color(SEAGULL_GRAY, bird_color, 0.18)
        body_color = _mix_color(SEAGULL_WHITE, bird_color, 0.1)
        highlight = _mix_color(body_color, (255, 255, 255), 0.45)
        pygame.draw.polygon(screen, BIRD_SHADOW, shadow_points)
        _draw_wing(
            screen, root=left_root, tip=left_tip, outer=left_outer, color=wing_color
        )
        _draw_wing(
            screen,
            root=right_root,
            tip=right_tip,
            outer=right_outer,
            color=wing_color,
        )
        pygame.draw.line(screen, SEAGULL_DARK_TIP, left_tip, left_outer, 1)
        pygame.draw.line(screen, SEAGULL_DARK_TIP, right_tip, right_outer, 1)
        pygame.draw.line(screen, body_color, nose, tail, 2)
        pygame.draw.line(screen, highlight, nose, center, 1)
        pygame.draw.line(screen, SEAGULL_BEAK, nose, beak, 1)
        if bird.phase % 1.0 < 0.28:
            pygame.draw.line(screen, WING_HIGHLIGHT, left_root, left_tip, 1)


def _create_bird(rng: random.Random, *, width: int, height: int) -> Bird:
    angle = rng.uniform(-0.3, 0.3)
    speed = rng.uniform(MIN_SPEED, MAX_SPEED)
    return Bird(
        x=rng.uniform(0, width),
        y=rng.uniform(8, max(9, height - 8)),
        vx=math.cos(angle) * speed,
        vy=math.sin(angle) * speed,
        phase=rng.random() * math.tau,
    )


def _wrapped_delta(delta: float, width: int) -> float:
    if width <= 0:
        return delta
    half_width = width / 2
    if delta > half_width:
        return delta - width
    if delta < -half_width:
        return delta + width
    return delta


def _clamp_velocity(vx: float, vy: float) -> tuple[float, float]:
    speed = math.hypot(vx, vy)
    if speed < 0.001:
        return (MIN_SPEED, 0.0)
    if speed < MIN_SPEED:
        scale = MIN_SPEED / speed
        return (vx * scale, vy * scale)
    if speed > MAX_SPEED:
        scale = MAX_SPEED / speed
        return (vx * scale, vy * scale)
    return (vx, vy)


def _controlled_hue(
    *,
    hue_degrees: float,
    gamepad: GamepadSnapshot,
    dt: float,
) -> float:
    if not gamepad.connected:
        return hue_degrees
    hue_delta = (
        (
            _trigger_pressure(gamepad.axis_value(GamepadAxis.TRIGGER_RIGHT))
            - _trigger_pressure(gamepad.axis_value(GamepadAxis.TRIGGER_LEFT))
        )
        * HUE_DEGREES_PER_SECOND
        * dt
    )
    return (hue_degrees + hue_delta) % 360.0


def _bird_color(hue_degrees: float) -> tuple[int, int, int]:
    red, green, blue = hsv_to_rgb((hue_degrees % 360.0) / 360.0, 0.34, 1.0)
    tint = (round(red * 255), round(green * 255), round(blue * 255))
    return _mix_color(SEAGULL_WHITE, tint, 0.32)


def _bird_tint(
    color: tuple[int, int, int],
    *,
    depth: float,
    phase: float,
) -> tuple[int, int, int]:
    warmth = 0.08 + (math.sin(phase * 3.0) + 1.0) * 0.05
    lit = _mix_color(color, WING_HIGHLIGHT, warmth)
    return _mix_color(lit, (255, 255, 255), max(0.0, min(depth, 1.0)) * 0.18)


def _trigger_pressure(raw_value: float) -> float:
    return max(0.0, min(raw_value, 1.0))


def _mix_color(
    first: tuple[int, int, int],
    second: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    ratio = max(0.0, min(ratio, 1.0))
    return tuple(
        round(first[index] * (1.0 - ratio) + second[index] * ratio)
        for index in range(3)
    )


def _translate_points(
    points: list[tuple[int, int]],
    offset: tuple[int, int],
) -> list[tuple[int, int]]:
    return [(x + offset[0], y + offset[1]) for x, y in points]


def _draw_moon(screen: pygame.Surface, *, width: int) -> None:
    center = (max(12, width - 28), 11)
    pygame.draw.circle(screen, _mix_color(MOON_COLOR, SKY_TOP, 0.12), center, 5)
    pygame.draw.circle(screen, MOON_COLOR, center, 3)
    pygame.draw.circle(screen, SKY_TOP, (center[0] + 2, center[1] - 1), 3)


def _draw_cloud_band(
    screen: pygame.Surface,
    *,
    width: int,
    y: int,
    offset: int,
) -> None:
    for x in range(-offset, width + 24, 48):
        color = _mix_color(CLOUD_COLOR, SKY_MIDDLE, 0.36)
        pygame.draw.line(screen, color, (x, y), (x + 18, y), 1)
        pygame.draw.line(
            screen,
            _mix_color(color, SKY_BOTTOM, 0.25),
            (x + 7, y + 1),
            (x + 31, y + 1),
            1,
        )


def _draw_wing(
    screen: pygame.Surface,
    *,
    root: tuple[float, float],
    tip: tuple[float, float],
    outer: tuple[float, float],
    color: tuple[int, int, int],
) -> None:
    pygame.draw.line(screen, color, root, tip, 2)
    pygame.draw.line(screen, _mix_color(color, SEAGULL_WHITE, 0.22), tip, outer, 1)


def _offset(
    point: tuple[float, float],
    direction: tuple[float, float],
    distance: float,
) -> tuple[float, float]:
    return (
        point[0] + direction[0] * distance,
        point[1] + direction[1] * distance,
    )
