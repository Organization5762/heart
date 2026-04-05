"""Validate beat-driven Pranay sketch state updates so choreography stays synced to tempo."""

from __future__ import annotations

import pygame

from heart.display.color import Color
from heart.renderers.pranay_sketch.provider import (PranaySketchStateProvider,
                                                    enhance_piece_image)
from heart.renderers.pranay_sketch.state import PranaySketchState


class TestPranaySketchStateProvider:
    """Exercise beat counters and bar triggers so the segmented dance stays musically structured as timings evolve."""

    def test_enhance_piece_image_boosts_color_and_opacity(self) -> None:
        """Verify piece enhancement increases saturation and visible edge opacity so the drawings read more clearly on the physical display."""

        surface = pygame.Surface((1, 1), pygame.SRCALPHA)
        surface.fill((120, 90, 90, 128))

        enhanced = enhance_piece_image(surface)
        pixel = enhanced.get_at((0, 0))

        assert pixel.a > 128
        assert pixel.r > pixel.g
        assert pixel.r > 120

    def test_enhance_piece_image_turns_dark_monochrome_strokes_white(self) -> None:
        """Verify low-saturation dark sketch lines become white so the stick figures stay visible after the mode switches to a dark stage background."""

        surface = pygame.Surface((1, 1), pygame.SRCALPHA)
        surface.fill((40, 40, 40, 96))

        enhanced = enhance_piece_image(surface)
        pixel = enhanced.get_at((0, 0))

        assert pixel.r == 255
        assert pixel.g == 255
        assert pixel.b == 255
        assert pixel.a >= 96

    def test_advance_state_flips_layout_on_every_sixteenth_beat(self) -> None:
        """Verify the sixteenth beat toggles the mirrored layout so larger position swaps land less often and feel more intentional."""

        provider = PranaySketchStateProvider(fallback_bpm=120)
        state = self._build_state(
            active_bpm=120,
            beat_count=15,
            beat_elapsed_s=0.49,
            layout_flipped=False,
            layout_flip_elapsed_s=0.5,
            bar_burst_elapsed_s=None,
        )

        updated = provider._advance_state(state=state, elapsed_s=0.02)

        assert updated.beat_count == 16
        assert updated.layout_flipped is True
        assert updated.layout_flip_elapsed_s == 0.0
        assert updated.bar_burst_elapsed_s is None

    def test_advance_state_triggers_bar_burst_every_sixty_fourth_beat(self) -> None:
        """Verify the sixty-fourth beat starts the special burst phrase so the biggest accent arrives only once in a longer musical phrase."""

        provider = PranaySketchStateProvider(fallback_bpm=120)
        state = self._build_state(
            active_bpm=120,
            beat_count=63,
            beat_elapsed_s=0.49,
            layout_flipped=True,
            layout_flip_elapsed_s=0.5,
            bar_burst_elapsed_s=None,
        )

        updated = provider._advance_state(state=state, elapsed_s=0.02)

        assert updated.beat_count == 64
        assert updated.layout_flipped is False
        assert updated.layout_flip_elapsed_s == 0.0
        assert updated.bar_burst_elapsed_s == 0.0

    def _build_state(
        self,
        *,
        active_bpm: int,
        beat_count: int,
        beat_elapsed_s: float,
        layout_flipped: bool,
        layout_flip_elapsed_s: float,
        bar_burst_elapsed_s: float | None,
    ) -> PranaySketchState:
        return PranaySketchState(
            canvas_size=64,
            pieces=(),
            background_color=Color(252, 251, 247),
            grid_color=Color(212, 214, 220),
            active_bpm=active_bpm,
            beat_count=beat_count,
            beat_elapsed_s=beat_elapsed_s,
            layout_flipped=layout_flipped,
            layout_flip_elapsed_s=layout_flip_elapsed_s,
            bar_burst_elapsed_s=bar_burst_elapsed_s,
        )
