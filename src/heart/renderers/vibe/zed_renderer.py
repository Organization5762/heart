from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

ZED_FONT_PATH = Path("src/heart/assets/Grand9K Pixel.ttf")
ZED_BACKGROUND = (6, 0, 0)
ZED_TEXT = (255, 36, 24)
ZED_SHADOW = (96, 0, 0)
ZED_SEQUENCE: tuple[tuple[str, int], ...] = (
    ("what is", 1200),
    ("something", 1200),
    ("people", 1200),
    ("are not", 1200),
    ("ready", 1200),
    ("to hear?", 1200),
    ("", 1200),
    ("ZEDS\nDEAD", 1900),
    ("", 1200),
)


@dataclass(frozen=True)
class ZedState:
    start_ticks_ms: int


class ZedRenderer(StatefulBaseRenderer[ZedState]):
    def __init__(self) -> None:
        super().__init__()
        self._font_cache: dict[tuple[int, int, bool], pygame.font.Font] = {}
        self._layout_cache: dict[
            tuple[int, int, str, bool], tuple[pygame.font.Font, tuple[str, ...]]
        ] = {}

    def _create_initial_state(
        self,
        *,
        window: DisplayContext,
        peripheral_manager,
        orientation: Orientation,
    ) -> ZedState:
        del window, peripheral_manager, orientation
        return ZedState(start_ticks_ms=pygame.time.get_ticks())

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        state = self.state
        window.fill(ZED_BACKGROUND)

        elapsed_ms = pygame.time.get_ticks() - state.start_ticks_ms
        text = self._current_text(elapsed_ms)
        if not text:
            return

        width, height = window.get_size()
        is_final_hit = text == "ZEDS\nDEAD"
        font, lines = self._fit_layout(text, width, height, is_final_hit)
        text_color = (255, 235, 88) if is_final_hit else ZED_TEXT
        shadow_color = (148, 16, 0) if is_final_hit else ZED_SHADOW
        line_surfaces = [font.render(line, False, text_color) for line in lines]
        shadow_surfaces = [font.render(line, False, shadow_color) for line in lines]
        line_height = font.get_linesize()
        total_height = line_height * len(line_surfaces)
        y = (height - total_height) // 2

        for rendered, shadow in zip(line_surfaces, shadow_surfaces):
            text_width, _ = rendered.get_size()
            x = (width - text_width) // 2

            if is_final_hit:
                for dx, dy in ((3, 0), (-3, 0), (0, 3), (0, -3), (2, 2), (-2, 2)):
                    window.blit(shadow, (x + dx, y + dy))
            else:
                # Slight teleprompter bleed on the regular cards.
                window.blit(shadow, (x + 2, y))
                window.blit(shadow, (x - 2, y))
                window.blit(shadow, (x, y + 2))
            window.blit(rendered, (x, y))
            y += line_height

    def _current_text(self, elapsed_ms: int) -> str:
        total = sum(duration for _, duration in ZED_SEQUENCE)
        position = elapsed_ms % total
        running = 0
        for text, duration in ZED_SEQUENCE:
            running += duration
            if position < running:
                return text
        return ZED_SEQUENCE[-1][0]

    def _fit_layout(
        self,
        text: str,
        width: int,
        height: int,
        is_final_hit: bool,
    ) -> tuple[pygame.font.Font, tuple[str, ...]]:
        key = (width, height, text, is_final_hit)
        cached = self._layout_cache.get(key)
        if cached is not None:
            return cached

        font = self._font_for_size(width, height, is_final_hit)
        max_width = int(width * (0.96 if is_final_hit else 0.88))
        lines = (
            tuple(text.splitlines())
            if is_final_hit
            else self._wrap_text(text, font, max_width)
        )
        self._layout_cache[key] = (font, lines)
        return font, lines

    def _font_for_size(
        self, width: int, height: int, is_final_hit: bool
    ) -> pygame.font.Font:
        key = (width, height, is_final_hit)
        cached = self._font_cache.get(key)
        if cached is not None:
            return cached

        if is_final_hit:
            size = max(18, int(height * 0.63))
            sample_lines = ("ZEDS", "DEAD")
            max_width_ratio = 0.98
            max_height_ratio = 0.86
        else:
            size = max(12, int(height * 0.24))
            sample_lines = ("something", "to hear?")
            max_width_ratio = 0.88
            max_height_ratio = 0.58

        best = pygame.font.Font(str(ZED_FONT_PATH), size)
        while size >= 12:
            font = pygame.font.Font(str(ZED_FONT_PATH), size)
            widths = [
                font.render(line, False, ZED_TEXT).get_width() for line in sample_lines
            ]
            total_height = font.get_linesize() * len(sample_lines)
            if (
                max(widths) <= width * max_width_ratio
                and total_height <= height * max_height_ratio
            ):
                best = font
                break
            size -= 1

        self._font_cache[key] = best
        return best

    def _wrap_text(
        self,
        text: str,
        font: pygame.font.Font,
        max_width: int,
    ) -> tuple[str, ...]:
        words = text.split()
        if not words:
            return tuple()

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.render(candidate, False, ZED_TEXT).get_width() <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return tuple(lines)
