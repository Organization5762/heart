from __future__ import annotations

import textwrap
from typing import Iterable

import pygame
import reactivex
from reactivex import operators as ops
from reactivex.subject import BehaviorSubject

from heart.assets.loader import Loader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.free_text.state import FreeTextRendererState


class FreeTextStateProvider(ObservableProvider[FreeTextRendererState]):
    def __init__(self) -> None:
        self._text = BehaviorSubject("Waiting for text...")
        self._font_cache: dict[int, pygame.font.Font] = {}
        self._font_size_max: int = 12
        self._font_size_min: int = 6
        self._initial_font_size: int = 10

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[FreeTextRendererState]:
        windows = peripheral_manager.window.pipe(
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: window.get_size()),
            ops.distinct_until_changed(),
            ops.share(),
        )

        ticks = peripheral_manager.game_tick

        def to_state(latest: tuple[object | None, tuple[int, int], str]) -> FreeTextRendererState:
            _, window_size, text = latest
            width, height = window_size
            font_size, wrapped_lines, line_height = self._fit_font_and_wrap(
                text=text, window_width=width, window_height=height
            )
            return FreeTextRendererState(
                text=text,
                wrapped_lines=tuple(wrapped_lines),
                window_size=window_size,
                font_size=font_size,
                line_height=line_height,
            )

        return ticks.pipe(
            ops.with_latest_from(windows, self._text),
            ops.map(to_state),
            ops.start_with(self.initial_state()),
            ops.distinct_until_changed(),
            ops.share(),
        )

    def initial_state(self) -> FreeTextRendererState:
        return FreeTextRendererState(
            text=self._text.value,
            wrapped_lines=tuple(),
            window_size=(0, 0),
            font_size=self._initial_font_size,
            line_height=0,
        )

    def set_text(self, text: str) -> None:
        self._text.on_next(text)

    def get_font(self, size: int) -> pygame.font.Font:
        if size not in self._font_cache:
            self._font_cache[size] = Loader.load_font("Grand9K Pixel.ttf", font_size=size)
        return self._font_cache[size]

    def _fit_font_and_wrap(
        self, text: str, window_width: int, window_height: int
    ) -> tuple[int, Iterable[str], int]:
        """Return font size, wrapped lines, and line height that fit *text* on screen."""

        if window_width <= 0 or window_height <= 0:
            font = self.get_font(self._initial_font_size)
            return self._initial_font_size, [], font.get_linesize()

        for size in range(self._font_size_max, self._font_size_min - 1, -1):
            font_candidate = self.get_font(size)

            char_width = max(1, font_candidate.size("M")[0])
            max_chars_per_line = max(1, window_width // char_width)

            wrapped: list[str] = []
            for paragraph in text.split("\n"):
                wrapped_lines = textwrap.wrap(
                    paragraph, width=max_chars_per_line, break_long_words=False
                ) or [""]
                wrapped.extend(wrapped_lines)

            max_line_width_px = 0
            for line in wrapped:
                line_width_px = font_candidate.size(line)[0]
                if line_width_px > max_line_width_px:
                    max_line_width_px = line_width_px

            total_height_px = len(wrapped) * font_candidate.get_linesize()

            if max_line_width_px <= window_width and total_height_px <= window_height:
                return size, wrapped, font_candidate.get_linesize()

        fallback_font = self.get_font(self._font_size_min)
        char_width = max(1, fallback_font.size("M")[0])
        max_chars_per_line = max(1, window_width // char_width)
        wrapped: list[str] = []
        for paragraph in text.split("\n"):
            wrapped_lines = textwrap.wrap(
                paragraph, width=max_chars_per_line, break_long_words=False
            ) or [""]
            wrapped.extend(wrapped_lines)

        return self._font_size_min, wrapped, fallback_font.get_linesize()
