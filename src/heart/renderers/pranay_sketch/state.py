from __future__ import annotations

from dataclasses import dataclass

import pygame

from heart.display.color import Color


@dataclass(frozen=True)
class PranaySketchPiece:
    index: int
    image: pygame.Surface
    center_x: float
    center_y: float
    width: int
    height: int
    bob_amplitude_px: float
    sway_amplitude_px: float
    pulse_amplitude: float
    phase_offset: float
    entrance_delay_seconds: float


@dataclass(frozen=True)
class PranaySketchState:
    canvas_size: int
    pieces: tuple[PranaySketchPiece, ...]
    background_color: Color
    grid_color: Color
    active_bpm: int
    beat_count: int
    beat_elapsed_s: float
    layout_flipped: bool
    layout_flip_elapsed_s: float
    bar_burst_elapsed_s: float | None
