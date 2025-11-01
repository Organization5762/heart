import textwrap
from typing import Optional

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.phone_text import PhoneText


class FreeTextRenderer(BaseRenderer):
    """Render the most recent text message that arrived via *PhoneText*."""

    def __init__(self) -> None:
        """Create a *FreeTextRenderer*.

        Parameters
        ----------
        font_path:
            Filename inside the *assets* directory to load as a font.  If *None*
            the default pygame system font is used.
        font_size:
            Font size in pixels.
        color:
            RGB colour for the text.
        wrap_at_chars:
            Soft wrap column when incoming text does not contain new‐lines.  Set
            to *None* to disable wrapping.

        """
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED

        self._font: Optional[pygame.font.Font] = None
        self._phone_text: Optional[PhoneText] = None
        self._line_height: int = 0  # Store line height as instance variable

        # Dynamic sizing helpers
        self._cached_text: str | None = None  # Last text we rendered
        self._wrapped_lines: list[str] = []  # Cached wrapped lines for drawing
        self._last_window_size: tuple[int, int] | None = (
            None  # Cache of last window size used for sizing
        )

        # Font size bounds (inclusive)
        self._font_size_max: int = 12
        self._font_size_min: int = 6

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # Locate the PhoneText peripheral once – it's expected to be present if
        # this renderer is used, but we handle the case where it isn't to avoid
        # crashes.
        self._phone_text = peripheral_manager.get_phone_text()

        self._font = Loader.load_font("Grand9K Pixel.ttf")
        if self._font:
            self._line_height = self._font.get_linesize()

        super().initialize(window, clock, peripheral_manager, orientation)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fit_font_and_wrap(
        self, text: str, window_width: int, window_height: int
    ) -> tuple[pygame.font.Font, list[str]]:
        """Return a font (within bounds) and wrapped lines that fit *text* on screen.

        The function iterates from the largest to the smallest allowed font size and
        picks the first one where every wrapped line fits horizontally and the
        accumulated height fits vertically.  If *no* font size satisfies those
        constraints we fall back to the minimum size.

        """

        # Iterate from largest to smallest size to find the best fit.
        for size in range(self._font_size_max, self._font_size_min - 1, -1):
            font_candidate = Loader.load_font("Grand9K Pixel.ttf", font_size=size)

            # Approximate the maximum number of characters per line based on the
            # width of the character "M", which is usually close to the widest
            # glyph in monospace pixel fonts.  Ensure at least 1 char.
            char_width = max(1, font_candidate.size("M")[0])
            max_chars_per_line = max(1, window_width // char_width)

            # Perform soft wrapping for each paragraph using that limit.
            wrapped: list[str] = []
            for paragraph in text.split("\n"):
                # Use textwrap with break_long_words=False to avoid cutting words
                wrapped_lines = textwrap.wrap(
                    paragraph, width=max_chars_per_line, break_long_words=False
                ) or [""]
                wrapped.extend(wrapped_lines)

            # Calculate dimensions.
            max_line_width_px = 0
            for line in wrapped:
                line_width_px = font_candidate.size(line)[0]
                if line_width_px > max_line_width_px:
                    max_line_width_px = line_width_px

            total_height_px = len(wrapped) * font_candidate.get_linesize()

            # Check if the text fits.
            if max_line_width_px <= window_width and total_height_px <= window_height:
                return font_candidate, wrapped

        # If nothing fit, return the smallest size anyway.
        fallback_font = Loader.load_font(
            "Grand9K Pixel.ttf", font_size=self._font_size_min
        )
        # Basic wrapping with very small char count to avoid overly long lines.
        char_width = max(1, fallback_font.size("M")[0])
        max_chars_per_line = max(1, window_width // char_width)
        wrapped: list[str] = []
        for paragraph in text.split("\n"):
            # Use break_long_words=False here too for consistency
            wrapped_lines = textwrap.wrap(
                paragraph, width=max_chars_per_line, break_long_words=False
            ) or [""]
            wrapped.extend(wrapped_lines)

        return fallback_font, wrapped

    # ------------------------------------------------------------------
    # Render loop
    # ------------------------------------------------------------------
    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # Fetch the most recent text (or a placeholder).
        last_text: str | None = (
            self._phone_text.get_last_text()
            if self._phone_text
            else "Waiting for text..."
        )

        # Skip rendering if we have nothing to show.
        if not last_text:
            return

        window_width, window_height = window.get_size()

        # Recalculate font/wrapping if the text or available space changed.
        if (
            last_text != self._cached_text
            or self._last_window_size != (window_width, window_height)
            or self._font is None
        ):
            self._font, self._wrapped_lines = self._fit_font_and_wrap(
                last_text, window_width, window_height
            )
            self._cached_text = last_text
            self._last_window_size = (window_width, window_height)

            # Update line height for the current font
            self._line_height = self._font.get_linesize()

        # Calculate how many lines can fit in the window height
        max_lines_visible = max(1, window_height // self._line_height)

        # Truncate lines to only show what fits in the window
        visible_lines = self._wrapped_lines[:max_lines_visible]

        # Calculate total height of visible lines
        total_height = len(visible_lines) * self._line_height

        # Calculate vertical centring.
        y = (window_height - total_height) // 2

        # Draw each line centred horizontally.
        for line in visible_lines:
            rendered = self._font.render(line, True, (255, 105, 180))
            text_width, _ = rendered.get_size()
            x = (window_width - text_width) // 2
            window.blit(rendered, (x, y))
            y += self._line_height
