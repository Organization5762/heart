from __future__ import annotations

import textwrap
from typing import Iterable

import pygame
from manyfold import StreamNode
from manyfold.architecture import Value

from heart.assets.loader import Loader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.free_text.state import FreeTextRendererState

PIXEL_FONT_PATH = "Grand9K Pixel.ttf"
FONT_SIZE_MAX = 30
FONT_SIZE_MIN = 6
INITIAL_FONT_SIZE = 10
DEFAULT_TEXT = ""
TEXT_PADDING_PX = 4


class FreeTextStateProvider(ObservableProvider[FreeTextRendererState]):
    def __init__(self) -> None:
        self._text = Value.initialized(DEFAULT_TEXT)
        self._font_cache: dict[int, pygame.font.Font] = {}
        self._font_size_max: int = FONT_SIZE_MAX
        self._font_size_min: int = FONT_SIZE_MIN
        self._initial_font_size: int = INITIAL_FONT_SIZE

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> StreamNode[FreeTextRendererState]:
        windows = (
            peripheral_manager.window.filter(lambda window: window is not None)
            .map(lambda window: window.get_size())
            .distinct_until_changed()
        )
        frame_ticks = peripheral_manager.input_io.frame_tick_stream()

        def to_state(
            latest: tuple[object | None, tuple[int, int], str],
        ) -> FreeTextRendererState:
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

        return (
            frame_ticks.with_latest_from(windows, self._text)
            .map(to_state)
            .start_with(self.initial_state())
            .distinct_until_changed()
        )

    def initial_state(self) -> FreeTextRendererState:
        return FreeTextRendererState(
            text=self._text.latest or DEFAULT_TEXT,
            wrapped_lines=tuple(),
            window_size=(0, 0),
            font_size=self._initial_font_size,
            line_height=0,
        )

    def set_text(self, text: str) -> None:
        self._text.set(text)

    def get_font(self, size: int) -> pygame.font.Font:
        if size not in self._font_cache:
            self._font_cache[size] = Loader.load_font(PIXEL_FONT_PATH, font_size=size)
        return self._font_cache[size]

    def _fit_font_and_wrap(
        self, text: str, window_width: int, window_height: int
    ) -> tuple[int, Iterable[str], int]:
        """Return font size, wrapped lines, and line height that fit *text* on screen."""
        if window_width <= 0 or window_height <= 0:
            font = self.get_font(self._initial_font_size)
            return (self._initial_font_size, [], font.get_linesize())
        available_width = max(1, window_width - (TEXT_PADDING_PX * 2))
        available_height = max(1, window_height - (TEXT_PADDING_PX * 2))
        for size in range(self._font_size_max, self._font_size_min - 1, -1):
            font_candidate = self.get_font(size)
            char_width = max(1, font_candidate.size("M")[0])
            max_chars_per_line = max(1, available_width // char_width)
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
            if (
                max_line_width_px <= available_width
                and total_height_px <= available_height
            ):
                return (size, wrapped, font_candidate.get_linesize())
        fallback_font = self.get_font(self._font_size_min)
        char_width = max(1, fallback_font.size("M")[0])
        max_chars_per_line = max(1, available_width // char_width)
        wrapped: list[str] = []
        for paragraph in text.split("\n"):
            wrapped_lines = textwrap.wrap(
                paragraph, width=max_chars_per_line, break_long_words=False
            ) or [""]
            wrapped.extend(wrapped_lines)
        return (self._font_size_min, wrapped, fallback_font.get_linesize())

    def fit_text_to_window(
        self, text: str, window_width: int, window_height: int
    ) -> tuple[pygame.font.Font, tuple[str, ...], int]:
        font_size, wrapped_lines, line_height = self._fit_font_and_wrap(
            text=text,
            window_width=window_width,
            window_height=window_height,
        )
        return self.get_font(font_size), tuple(wrapped_lines), line_height
