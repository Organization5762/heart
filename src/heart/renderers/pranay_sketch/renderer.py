from __future__ import annotations

import math
import time

import pygame

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.pranay_sketch.provider import PranaySketchStateProvider
from heart.renderers.pranay_sketch.state import (PranaySketchPiece,
                                                 PranaySketchState)
from heart.runtime.display_context import DisplayContext

GRID_SPACING_PX = 8
GRID_DOT_RADIUS_PX = 1
TARGET_SIZE_RATIO = 0.88
COMPOSITION_VERTICAL_OFFSET_RATIO = 0.12
GLOBAL_FLOAT_AMPLITUDE_PX = 2.0
GLOBAL_FLOAT_FREQUENCY_HZ = 0.45
PIECE_ENTRANCE_DURATION_SECONDS = 0.8
PIECE_ENTRY_OFFSET_PX = 12
MIN_ENTRANCE_SCALE = 0.28
LAYOUT_FLIP_DURATION_BEATS = 1.0
LAYOUT_FLIP_SPIN_DEGREES = 28.0
BEAT_PULSE_WINDOW = 0.45
BEAT_PULSE_SCALE = 0.08
BAR_BURST_ORBIT_TURNS = 0.85
BAR_BURST_RADIUS_PX = 7.5
BAR_BURST_SCALE = 0.18
BAR_BURST_ROTATION_DEGREES = 42.0
BAR_BURST_DURATION_BEATS = 2.0
MIN_RENDER_SCALE = 0.08


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _ease_out_cubic(value: float) -> float:
    progress = _clamp01(value)
    return 1.0 - pow(1.0 - progress, 3)


def _ease_out_back(value: float) -> float:
    progress = _clamp01(value)
    overshoot = 1.70158
    return 1.0 + (overshoot + 1.0) * pow(progress - 1.0, 3) + overshoot * pow(
        progress - 1.0, 2
    )


def _ease_in_out_sine(value: float) -> float:
    progress = _clamp01(value)
    return 0.5 - (0.5 * math.cos(progress * math.pi))


class PranaySketchRenderer(StatefulBaseRenderer[PranaySketchState]):
    def __init__(self, provider: PranaySketchStateProvider | None = None) -> None:
        self._provider = provider or PranaySketchStateProvider(
            burst_duration_beats=BAR_BURST_DURATION_BEATS
        )
        super().__init__(builder=self._provider)
        self._start_monotonic_s: float | None = None

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._start_monotonic_s = time.monotonic()
        super().initialize(window, peripheral_manager, orientation)

    def reset(self) -> None:
        self._start_monotonic_s = None
        super().reset()

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if self._start_monotonic_s is None:
            self._start_monotonic_s = time.monotonic()

        assert window.screen is not None
        elapsed_seconds = max(0.0, time.monotonic() - self._start_monotonic_s)
        width, height = window.get_size()
        canvas_size_px = max(1, int(min(width, height) * TARGET_SIZE_RATIO))
        origin_x = (width - canvas_size_px) / 2
        origin_y = ((height - canvas_size_px) / 2) + (
            canvas_size_px * COMPOSITION_VERTICAL_OFFSET_RATIO
        )
        global_float_y = GLOBAL_FLOAT_AMPLITUDE_PX * math.sin(
            elapsed_seconds * math.tau * GLOBAL_FLOAT_FREQUENCY_HZ
        )

        window.fill(self.state.background_color._as_tuple())
        self._draw_grid(window)
        for piece in self.state.pieces:
            self._draw_piece(
                screen=window.screen,
                piece=piece,
                elapsed_seconds=elapsed_seconds,
                canvas_size_px=canvas_size_px,
                origin_x=origin_x,
                origin_y=origin_y + global_float_y,
            )

    def _draw_piece(
        self,
        screen: pygame.Surface,
        piece: PranaySketchPiece,
        elapsed_seconds: float,
        canvas_size_px: int,
        origin_x: float,
        origin_y: float,
    ) -> None:
        beat_duration_s = 60.0 / max(self.state.active_bpm, 1)
        piece_elapsed = max(0.0, elapsed_seconds - piece.entrance_delay_seconds)
        entrance_progress = _clamp01(piece_elapsed / PIECE_ENTRANCE_DURATION_SECONDS)
        entrance_scale = MIN_ENTRANCE_SCALE + (
            (1.0 - MIN_ENTRANCE_SCALE) * _ease_out_back(entrance_progress)
        )
        dance_mix = _ease_out_cubic(entrance_progress)
        beat_pulse = self._beat_pulse(beat_duration_s)
        pulse_scale = 1.0 + (beat_pulse * BEAT_PULSE_SCALE)
        mirrored_mix = self._mirrored_mix(beat_duration_s)
        burst_wave, burst_angle = self._bar_burst_motion(piece, beat_duration_s)
        phase = (elapsed_seconds * math.tau * 1.05) + piece.phase_offset
        scale = max(
            MIN_RENDER_SCALE,
            (canvas_size_px / self.state.canvas_size)
            * entrance_scale
            * pulse_scale
            * (1.0 + (burst_wave * BAR_BURST_SCALE)),
        )

        center_x = self._interpolate_piece_x(piece, mirrored_mix)
        center_y = piece.center_y
        canvas_center = self.state.canvas_size / 2
        radial_x = center_x - canvas_center
        radial_y = center_y - canvas_center
        radial_length = max(1.0, math.hypot(radial_x, radial_y))
        center_x += (radial_x / radial_length) * burst_wave * BAR_BURST_RADIUS_PX
        center_y += (radial_y / radial_length) * burst_wave * BAR_BURST_RADIUS_PX
        center_x += math.cos(burst_angle) * burst_wave * 3.0
        center_y += math.sin(burst_angle) * burst_wave * 3.0

        center_x_px = origin_x + (center_x / self.state.canvas_size) * canvas_size_px
        center_y_px = origin_y + (center_y / self.state.canvas_size) * canvas_size_px
        center_x_px += piece.sway_amplitude_px * math.sin(phase) * dance_mix
        center_y_px += piece.bob_amplitude_px * math.sin((phase * 1.8) + 0.8) * dance_mix
        center_y_px -= (1.0 - _ease_out_back(entrance_progress)) * PIECE_ENTRY_OFFSET_PX

        rotation = self._rotation_degrees(
            piece=piece,
            phase=phase,
            mirrored_mix=mirrored_mix,
            burst_wave=burst_wave,
        )
        piece_surface = pygame.transform.rotozoom(piece.image, rotation, scale)
        alpha = max(0, min(255, int(round(255 * _ease_out_cubic(entrance_progress)))))
        if alpha < 255:
            piece_surface = piece_surface.copy()
            piece_surface.set_alpha(alpha)

        piece_rect = piece_surface.get_rect(
            center=(int(round(center_x_px)), int(round(center_y_px)))
        )
        screen.blit(piece_surface, piece_rect)

    def _beat_pulse(self, beat_duration_s: float) -> float:
        window = max(beat_duration_s * BEAT_PULSE_WINDOW, 0.001)
        return _ease_out_cubic(1.0 - _clamp01(self.state.beat_elapsed_s / window))

    def _mirrored_mix(self, beat_duration_s: float) -> float:
        flip_duration_s = max(beat_duration_s * LAYOUT_FLIP_DURATION_BEATS, 0.001)
        flip_progress = _ease_in_out_sine(
            self.state.layout_flip_elapsed_s / flip_duration_s
        )
        if self.state.layout_flipped:
            return flip_progress
        return 1.0 - flip_progress

    def _bar_burst_motion(
        self,
        piece: PranaySketchPiece,
        beat_duration_s: float,
    ) -> tuple[float, float]:
        burst_elapsed_s = self.state.bar_burst_elapsed_s
        if burst_elapsed_s is None:
            return 0.0, piece.phase_offset

        burst_duration_s = max(beat_duration_s * BAR_BURST_DURATION_BEATS, 0.001)
        burst_progress = _clamp01(burst_elapsed_s / burst_duration_s)
        burst_wave = math.sin(burst_progress * math.pi)
        burst_angle = piece.phase_offset + (burst_progress * math.tau * BAR_BURST_ORBIT_TURNS)
        return burst_wave, burst_angle

    def _interpolate_piece_x(
        self,
        piece: PranaySketchPiece,
        mirrored_mix: float,
    ) -> float:
        mirrored_x = self.state.canvas_size - piece.center_x
        return ((1.0 - mirrored_mix) * piece.center_x) + (mirrored_mix * mirrored_x)

    def _rotation_degrees(
        self,
        *,
        piece: PranaySketchPiece,
        phase: float,
        mirrored_mix: float,
        burst_wave: float,
    ) -> float:
        flip_spin = math.sin(mirrored_mix * math.pi) * LAYOUT_FLIP_SPIN_DEGREES
        flip_spin *= -1.0 if self.state.layout_flipped else 1.0
        flip_spin *= 1.0 if piece.index % 2 == 0 else -1.0
        idle_wobble = math.sin((phase * 0.7) + 0.3) * 4.0
        burst_spin = burst_wave * BAR_BURST_ROTATION_DEGREES
        burst_spin *= 1.0 if piece.index % 2 == 0 else -1.0
        return idle_wobble + (flip_spin * 1.2) + burst_spin

    def _draw_grid(self, window: DisplayContext) -> None:
        assert window.screen is not None
        width, height = window.get_size()
        color = self.state.grid_color._as_tuple()
        for x in range(0, width, GRID_SPACING_PX):
            for y in range(0, height, GRID_SPACING_PX):
                pygame.draw.circle(
                    window.screen,
                    color,
                    (x, y),
                    GRID_DOT_RADIUS_PX,
                )
