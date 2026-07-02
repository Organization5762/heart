from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos, pi, sin
from pathlib import Path
from typing import Any

import pygame
from manyfold.architecture import PubSubObservable

from heart.device import Orientation
from heart.peripheral.core.input import GamepadAxis, GamepadButton
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.core.variables import Variable
from heart.peripheral.switch import SwitchState
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

LIFE_PRESERVER_FONT_PATH = Path("src/heart/assets/Grand9K Pixel.ttf")
LIFE_PRESERVER_BACKGROUND = (11, 85, 132)
LIFE_PRESERVER_WATER = (17, 128, 174)
LIFE_PRESERVER_WHITE = (255, 244, 222)
LIFE_PRESERVER_RED = (232, 50, 37)
LIFE_PRESERVER_TASSEL = (255, 147, 43)
LIFE_PRESERVER_SHADOW = (7, 48, 78)
LIFE_PRESERVER_TEXT = (255, 252, 238)
LIFE_PRESERVER_TEXT_SHADOW = (89, 24, 32)
LIFE_PRESERVER_MESSAGE_LINES = ("Swim",)
LIFE_PRESERVER_ROTATION_DEGREES = -16
LIFE_PRESERVER_ROTATION_WOBBLE_DEGREES = 10
LIFE_PRESERVER_ROTATION_FLOAT_MS = 2600
LIFE_PRESERVER_CAPTION_FLOAT_MS = 1800
LIFE_PRESERVER_WAVE_FLOAT_MS = 2100


@dataclass(frozen=True)
class LifePreserverState:
    caption_elapsed_ms: float = 0.0
    caption_duration_scale: float = 0.0
    rotation_elapsed_ms: float = 0.0
    rotation_duration_scale: float = 0.0
    wave_elapsed_ms: float = 0.0
    gamepad: Any | None = None
    last_switch_rotation: float | None = None
    switch_state: SwitchState | None = None
    font_cache_key: tuple[int, int] | None = None
    font: pygame.font.Font | None = None


class LifePreserverProvider(ObservableProvider[LifePreserverState]):
    def initial_state(
        self,
        *,
        peripheral_manager: PeripheralManager,
    ) -> LifePreserverState:
        return LifePreserverState(gamepad=peripheral_manager.input_io.gamepad)

    def observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> Variable[LifePreserverState]:
        initial_state = self.initial_state(peripheral_manager=peripheral_manager)
        frame_ticks = peripheral_manager.input_io.frame_tick_stream()
        switches = peripheral_manager.input_io.main_switch_stream()
        switch_updates = switches.map(
            lambda switch_event: (
                lambda state: self.handle_switch(state, switch_event.state)
            )
        )
        tick_updates = frame_ticks.map(
            lambda frame_tick: (
                lambda state: self.advance(state, elapsed_ms=frame_tick.delta_ms)
            )
        )
        return PubSubObservable.merge(switch_updates, tick_updates).state(
            initial_state,
            lambda state, update: update(state),
        )

    def handle_switch(
        self,
        state: LifePreserverState,
        switch_state: SwitchState,
    ) -> LifePreserverState:
        caption_duration_scale = state.caption_duration_scale
        last_rotation = state.last_switch_rotation
        current_rotation = switch_state.rotation_since_last_button_press
        if last_rotation is None:
            last_rotation = current_rotation
        elif current_rotation > last_rotation:
            caption_duration_scale += 0.05
        elif current_rotation < last_rotation:
            caption_duration_scale -= 0.05
        return replace(
            state,
            caption_duration_scale=caption_duration_scale,
            last_switch_rotation=current_rotation,
            switch_state=switch_state,
        )

    def advance(
        self,
        state: LifePreserverState,
        *,
        elapsed_ms: float,
    ) -> LifePreserverState:
        state = self._apply_gamepad_input(state)
        return replace(
            state,
            caption_elapsed_ms=state.caption_elapsed_ms
            + elapsed_ms * _speed_multiplier(state.caption_duration_scale),
            rotation_elapsed_ms=state.rotation_elapsed_ms
            + elapsed_ms * _speed_multiplier(state.rotation_duration_scale),
            wave_elapsed_ms=state.wave_elapsed_ms + elapsed_ms,
        )

    def _apply_gamepad_input(
        self,
        state: LifePreserverState,
    ) -> LifePreserverState:
        gamepad_controller = state.gamepad
        if gamepad_controller is None:
            return state
        caption_duration_scale = state.caption_duration_scale
        rotation_duration_scale = state.rotation_duration_scale
        for event in gamepad_controller.sample():
            snapshot = event.snapshot
            bumper_pressed = snapshot.button_held(
                GamepadButton.ZL
            ) or snapshot.button_held(GamepadButton.ZR)
            left_trigger_pressure = _trigger_pressure(
                snapshot.axis_value(GamepadAxis.TRIGGER_LEFT)
            )
            right_trigger_pressure = _trigger_pressure(
                snapshot.axis_value(GamepadAxis.TRIGGER_RIGHT)
            )
            if bumper_pressed:
                caption_duration_scale += 0.005
            if right_trigger_pressure > 0.0:
                rotation_duration_scale += 0.005 * right_trigger_pressure
            if left_trigger_pressure > 0.0:
                rotation_duration_scale -= 0.005 * left_trigger_pressure
        return replace(
            state,
            caption_duration_scale=caption_duration_scale,
            rotation_duration_scale=rotation_duration_scale,
        )


class LifePreserverRenderer(StatefulBaseRenderer[LifePreserverState]):
    def __init__(self) -> None:
        super().__init__(builder=LifePreserverProvider())

    def _create_initial_state(
        self,
        *,
        window: DisplayContext,
        peripheral_manager,
        orientation: Orientation,
    ) -> LifePreserverState:
        del window, peripheral_manager, orientation
        return LifePreserverState()

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        surface = window.screen
        if surface is None:
            raise RuntimeError("Screen is not initialized")

        width, height = window.get_size()
        window.fill(LIFE_PRESERVER_BACKGROUND)
        self._draw_water(surface, width, height, self.state.wave_elapsed_ms)

        tile_size = min(width, height)
        center = (width // 2, round(height * 0.42))
        radius = max(12, round(tile_size * 0.30))
        text_margin = max(1, round(radius * 0.12))
        float_offset = round(
            sin(
                self.state.caption_elapsed_ms / LIFE_PRESERVER_CAPTION_FLOAT_MS * 2 * pi
            )
            * max(1, round(radius * 0.08))
        )
        text_rect = pygame.Rect(
            center[0] - radius + text_margin,
            center[1] - round(radius * 0.34) + float_offset,
            (radius - text_margin) * 2,
            round(radius * 0.68),
        )

        rotation_degrees = LIFE_PRESERVER_ROTATION_DEGREES + (
            sin(
                self.state.rotation_elapsed_ms
                / LIFE_PRESERVER_ROTATION_FLOAT_MS
                * 2
                * pi
            )
            * LIFE_PRESERVER_ROTATION_WOBBLE_DEGREES
        )
        self._draw_preserver(surface, center, radius, rotation_degrees)
        self._draw_message(surface, text_rect)

    def _draw_water(
        self,
        surface: pygame.Surface,
        width: int,
        height: int,
        elapsed_ms: float,
    ) -> None:
        phase = elapsed_ms / LIFE_PRESERVER_WAVE_FLOAT_MS * 2 * pi
        wave_shift = round(sin(phase) * 6)
        vertical_shift = round(sin(phase + pi / 2) * 2)
        for y in range(0, height, 8):
            offset = (4 if (y // 8) % 2 else 0) + wave_shift
            pygame.draw.arc(
                surface,
                LIFE_PRESERVER_WATER,
                pygame.Rect(-8 + offset, y + vertical_shift, 32, 14),
                0,
                pi,
                2,
            )
            for x in range(24 + offset, width + 24, 40):
                pygame.draw.arc(
                    surface,
                    LIFE_PRESERVER_WATER,
                    pygame.Rect(x, y + vertical_shift, 32, 14),
                    0,
                    pi,
                    2,
                )

    def _draw_preserver(
        self,
        surface: pygame.Surface,
        center: tuple[int, int],
        radius: int,
        rotation_degrees: float,
    ) -> None:
        ring_width = max(5, round(radius * 0.34))
        margin = ring_width + 8
        art_size = (radius + margin) * 2
        art = pygame.Surface((art_size, art_size), pygame.SRCALPHA)
        art_center = (art_size // 2, art_size // 2)
        self._draw_preserver_art(art, art_center, radius, ring_width)

        rotated = pygame.transform.rotate(art, rotation_degrees)
        rotated_rect = rotated.get_rect(center=center)
        surface.blit(rotated, rotated_rect)

    def _draw_preserver_art(
        self,
        surface: pygame.Surface,
        center: tuple[int, int],
        radius: int,
        ring_width: int,
    ) -> None:
        inner_radius = max(4, radius - ring_width)
        outer_rect = pygame.Rect(0, 0, radius * 2, radius * 2)
        outer_rect.center = center

        shadow_center = (center[0] + 3, center[1] + 3)
        pygame.draw.circle(surface, LIFE_PRESERVER_SHADOW, shadow_center, radius)
        pygame.draw.circle(surface, LIFE_PRESERVER_WHITE, center, radius)

        for start, end in (
            (-0.35 * pi, 0.35 * pi),
            (0.65 * pi, 1.35 * pi),
            (0.15 * pi, 0.35 * pi),
            (1.15 * pi, 1.35 * pi),
        ):
            pygame.draw.arc(
                surface,
                LIFE_PRESERVER_RED,
                outer_rect,
                start,
                end,
                ring_width,
            )

        pygame.draw.circle(surface, LIFE_PRESERVER_BACKGROUND, center, inner_radius)
        pygame.draw.circle(surface, LIFE_PRESERVER_RED, center, radius, 2)
        pygame.draw.circle(surface, LIFE_PRESERVER_WHITE, center, inner_radius + 1, 2)

        rope_radius = radius + max(2, ring_width // 4)
        for angle in (0, pi / 2, pi, 3 * pi / 2):
            x = center[0] + round(rope_radius * cos(angle))
            y = center[1] + round(rope_radius * sin(angle))
            pygame.draw.circle(
                surface,
                LIFE_PRESERVER_TEXT,
                (x, y),
                max(2, ring_width // 4),
            )
            self._draw_tassel(surface, (x, y), angle, ring_width)

    def _draw_tassel(
        self,
        surface: pygame.Surface,
        anchor: tuple[int, int],
        angle: float,
        ring_width: int,
    ) -> None:
        length = max(5, ring_width)
        spread = max(2, ring_width // 3)
        base_dx = cos(angle)
        base_dy = sin(angle)
        tangent_dx = -sin(angle)
        tangent_dy = cos(angle)
        for offset in (-spread, 0, spread):
            start = (
                anchor[0] + round(tangent_dx * offset),
                anchor[1] + round(tangent_dy * offset),
            )
            end = (
                start[0] + round(base_dx * length),
                start[1] + round(base_dy * length),
            )
            pygame.draw.line(surface, LIFE_PRESERVER_TASSEL, start, end, 2)

    def _draw_message(self, surface: pygame.Surface, text_rect: pygame.Rect) -> None:
        font = self._font_for_rect(text_rect)
        line_height = font.get_linesize()
        total_height = line_height * len(LIFE_PRESERVER_MESSAGE_LINES)
        y = text_rect.y + (text_rect.height - total_height) // 2

        for line in LIFE_PRESERVER_MESSAGE_LINES:
            shadow = font.render(line, False, LIFE_PRESERVER_TEXT_SHADOW)
            rendered = font.render(line, False, LIFE_PRESERVER_TEXT)
            x = text_rect.x + (text_rect.width - rendered.get_width()) // 2
            surface.blit(shadow, (x + 2, y + 2))
            surface.blit(rendered, (x, y))
            y += line_height

    def _font_for_rect(self, text_rect: pygame.Rect) -> pygame.font.Font:
        cache_key = (text_rect.width, text_rect.height)
        if self.state.font_cache_key == cache_key and self.state.font is not None:
            return self.state.font

        size = max(6, min(22, round(text_rect.height * 0.74)))
        best = pygame.font.Font(str(LIFE_PRESERVER_FONT_PATH), size)
        while size >= 6:
            font = pygame.font.Font(str(LIFE_PRESERVER_FONT_PATH), size)
            max_width = max(
                font.render(line, False, LIFE_PRESERVER_TEXT).get_width()
                for line in LIFE_PRESERVER_MESSAGE_LINES
            )
            total_height = font.get_linesize() * len(LIFE_PRESERVER_MESSAGE_LINES)
            if max_width <= text_rect.width and total_height <= text_rect.height:
                best = font
                break
            size -= 1

        self.update_state(font_cache_key=cache_key, font=best)
        return best


def _trigger_pressure(value: float) -> float:
    if value < 0:
        return max(0.0, (value + 1.0) / 2.0)
    return max(0.0, value)


def _speed_multiplier(duration_scale: float) -> float:
    effective_duration_scale = max(-0.9, min(0.9, duration_scale))
    return 1.0 / max(0.1, 1.0 - effective_duration_scale)
