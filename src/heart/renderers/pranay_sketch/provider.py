from __future__ import annotations

import pygame
import reactivex
from reactivex import operators as ops

from heart.assets.loader import Loader
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.heart_rates import current_bpms
from heart.renderers.pranay_sketch.state import (PranaySketchPiece,
                                                 PranaySketchState)
from heart.utilities.reactivex_threads import pipe_in_background

SEGMENT_DIRECTORY = "pranay_sketch_segments"
SEGMENT_LAYOUT_PATH = f"{SEGMENT_DIRECTORY}/layout.json"
DEFAULT_BACKGROUND_COLOR = Color(0, 0, 0)
DEFAULT_GRID_COLOR = Color(0, 0, 0)
DEFAULT_FALLBACK_BPM = 120
DEFAULT_BURST_DURATION_BEATS = 2.0
PIECE_ENTRANCE_STAGGER_SECONDS = 0.12
LAYOUT_FLIP_INTERVAL_BEATS = 16
BAR_BURST_INTERVAL_BEATS = 64
SATURATION_MULTIPLIER = 1.65
VALUE_MULTIPLIER = 1.1
CONTRAST_MULTIPLIER = 1.14
ALPHA_MULTIPLIER = 1.2
MIN_VISIBLE_ALPHA = 20
MIN_MONOCHROME_ALPHA = 6
MONOCHROME_SATURATION_THRESHOLD = 14.0
MONOCHROME_LUMINANCE_THRESHOLD = 120.0


def _clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def enhance_piece_image(image: pygame.Surface) -> pygame.Surface:
    """Boost piece saturation and edge opacity for LED-friendly rendering."""

    enhanced = image.copy()
    width, height = enhanced.get_size()
    for x in range(width):
        for y in range(height):
            pixel = enhanced.get_at((x, y))
            if pixel.a == 0:
                continue
            if pixel.a < MIN_VISIBLE_ALPHA:
                enhanced.set_at((x, y), (0, 0, 0, 0))
                continue

            working = pygame.Color(pixel.r, pixel.g, pixel.b, pixel.a)
            hue, saturation, value, alpha = working.hsva
            working.hsva = (
                hue,
                min(100.0, saturation * SATURATION_MULTIPLIER),
                min(100.0, value * VALUE_MULTIPLIER),
                alpha,
            )

            luminance = (
                (0.2126 * working.r)
                + (0.7152 * working.g)
                + (0.0722 * working.b)
            )
            if (
                saturation <= MONOCHROME_SATURATION_THRESHOLD
                and luminance <= MONOCHROME_LUMINANCE_THRESHOLD
            ):
                enhanced.set_at(
                    (x, y),
                    (
                        255,
                        255,
                        255,
                        _clamp_channel(max(pixel.a, MIN_MONOCHROME_ALPHA)),
                    ),
                )
                continue

            red = luminance + ((working.r - luminance) * CONTRAST_MULTIPLIER)
            green = luminance + ((working.g - luminance) * CONTRAST_MULTIPLIER)
            blue = luminance + ((working.b - luminance) * CONTRAST_MULTIPLIER)
            edge_alpha = _clamp_channel(
                max(MIN_VISIBLE_ALPHA, pixel.a) * ALPHA_MULTIPLIER
            )

            enhanced.set_at(
                (x, y),
                (
                    _clamp_channel(red),
                    _clamp_channel(green),
                    _clamp_channel(blue),
                    edge_alpha,
                ),
            )
    return enhanced


class PranaySketchStateProvider(ObservableProvider[PranaySketchState]):
    def __init__(
        self,
        fallback_bpm: int = DEFAULT_FALLBACK_BPM,
        burst_duration_beats: float = DEFAULT_BURST_DURATION_BEATS,
    ) -> None:
        self._fallback_bpm = fallback_bpm
        self._burst_duration_beats = burst_duration_beats
        self._initial_state: PranaySketchState | None = None

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[PranaySketchState]:
        frame_ticks = pipe_in_background(
            peripheral_manager.frame_tick_controller.observable(),
            ops.share(),
        )
        initial_state = self._load_initial_state()

        def advance_state(
            state: PranaySketchState,
            frame_tick: object,
        ) -> PranaySketchState:
            return self._advance_state(
                state=state,
                elapsed_s=max(float(frame_tick.delta_s), 0.0),
            )

        return pipe_in_background(
            frame_ticks,
            ops.scan(advance_state, seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

    def _load_initial_state(self) -> PranaySketchState:
        if self._initial_state is not None:
            return self._initial_state

        layout = Loader.load_json(SEGMENT_LAYOUT_PATH)
        pieces = tuple(
            self._create_piece(piece_layout)
            for piece_layout in layout.get("pieces", [])
            if isinstance(piece_layout, dict)
        )
        active_bpm = self._resolve_active_bpm()
        beat_duration_s = 60.0 / active_bpm
        self._initial_state = PranaySketchState(
            canvas_size=int(layout["canvas_size"]),
            pieces=pieces,
            background_color=DEFAULT_BACKGROUND_COLOR,
            grid_color=DEFAULT_GRID_COLOR,
            active_bpm=active_bpm,
            beat_count=0,
            beat_elapsed_s=0.0,
            layout_flipped=False,
            layout_flip_elapsed_s=beat_duration_s,
            bar_burst_elapsed_s=None,
        )
        return self._initial_state

    def _create_piece(self, layout: dict[str, object]) -> PranaySketchPiece:
        image = Loader.load(f"{SEGMENT_DIRECTORY}/{layout['file']}")
        if pygame.display.get_surface() is not None:
            image = image.convert_alpha()
        else:
            image = image.copy()
        image = enhance_piece_image(image)
        index = int(layout["index"])
        return PranaySketchPiece(
            index=index,
            image=image,
            center_x=float(layout["center_x"]),
            center_y=float(layout["center_y"]),
            width=int(layout["width"]),
            height=int(layout["height"]),
            bob_amplitude_px=1.6 + (index % 3) * 0.5,
            sway_amplitude_px=1.2 + ((index + 1) % 3) * 0.55,
            pulse_amplitude=0.04 + (index % 4) * 0.015,
            phase_offset=index * 0.63,
            entrance_delay_seconds=index * PIECE_ENTRANCE_STAGGER_SECONDS,
        )

    def _advance_state(
        self,
        *,
        state: PranaySketchState,
        elapsed_s: float,
    ) -> PranaySketchState:
        active_bpm = self._resolve_active_bpm()
        beat_duration_s = 60.0 / active_bpm
        beat_elapsed_s = state.beat_elapsed_s + elapsed_s
        layout_flip_elapsed_s = state.layout_flip_elapsed_s + elapsed_s
        bar_burst_elapsed_s = (
            None
            if state.bar_burst_elapsed_s is None
            else state.bar_burst_elapsed_s + elapsed_s
        )
        beat_count = state.beat_count
        layout_flipped = state.layout_flipped
        burst_duration_s = beat_duration_s * self._burst_duration_beats

        if bar_burst_elapsed_s is not None and bar_burst_elapsed_s >= burst_duration_s:
            bar_burst_elapsed_s = None

        while beat_elapsed_s >= beat_duration_s:
            beat_elapsed_s -= beat_duration_s
            beat_count += 1
            if beat_count % LAYOUT_FLIP_INTERVAL_BEATS == 0:
                layout_flipped = not layout_flipped
                layout_flip_elapsed_s = 0.0
            if beat_count % BAR_BURST_INTERVAL_BEATS == 0:
                bar_burst_elapsed_s = 0.0

        return PranaySketchState(
            canvas_size=state.canvas_size,
            pieces=state.pieces,
            background_color=state.background_color,
            grid_color=state.grid_color,
            active_bpm=active_bpm,
            beat_count=beat_count,
            beat_elapsed_s=beat_elapsed_s,
            layout_flipped=layout_flipped,
            layout_flip_elapsed_s=layout_flip_elapsed_s,
            bar_burst_elapsed_s=bar_burst_elapsed_s,
        )

    def _resolve_active_bpm(self) -> int:
        active_bpms = [bpm for bpm in current_bpms.values() if bpm > 0]
        if not active_bpms:
            return self._fallback_bpm
        return max(active_bpms)
