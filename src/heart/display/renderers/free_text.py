from __future__ import annotations

import textwrap
from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.events.types import PhoneTextMessage
from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import EventBus, SubscriptionHandle
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

_LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class FreeTextRendererState:
    cached_text: str | None = None
    wrapped_lines: tuple[str, ...] = ()
    window_size: tuple[int, int] | None = None
    font_size: int | None = None
    line_height: int = 0


class FreeTextRenderer(AtomicBaseRenderer[FreeTextRendererState]):
    """Render the most recent text message that arrived via *PhoneText*."""

    def __init__(self) -> None:
        """Create a *FreeTextRenderer*."""

        self._font_cache: dict[int, pygame.font.Font] = {}
        self._latest_text: str | None = None
        self._event_bus: EventBus | None = None
        self._subscription: SubscriptionHandle | None = None

        # Font size bounds (inclusive)
        self._font_size_max: int = 12
        self._font_size_min: int = 6
        self._initial_font_size: int = 10

        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED

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
        """Initialise the renderer and warm the default font cache."""

        self._ensure_subscription(peripheral_manager)

        initial_font = self._get_font(self._initial_font_size)
        self.update_state(
            font_size=self._initial_font_size,
            line_height=initial_font.get_linesize(),
        )

        super().initialize(window, clock, peripheral_manager, orientation)

    def reset(self) -> None:
        self._unsubscribe()
        self._latest_text = None
        super().reset()

    def _ensure_subscription(self, peripheral_manager: PeripheralManager) -> None:
        if self._subscription is not None:
            return
        bus = getattr(peripheral_manager, "event_bus", None)
        if bus is None:
            _LOGGER.debug("FreeTextRenderer missing event bus; text will remain static")
            return
        self._event_bus = bus
        self._subscription = bus.subscribe(
            PhoneTextMessage.EVENT_TYPE,
            self._handle_phone_text_event,
        )

    def _unsubscribe(self) -> None:
        if self._event_bus is None or self._subscription is None:
            self._event_bus = None
            self._subscription = None
            return
        try:
            self._event_bus.unsubscribe(self._subscription)
        except Exception:  # pragma: no cover - defensive cleanup
            _LOGGER.exception("Failed to unsubscribe FreeTextRenderer")
        finally:
            self._event_bus = None
            self._subscription = None

    def _handle_phone_text_event(self, event: Input) -> None:
        payload = event.data
        if isinstance(payload, PhoneTextMessage):
            text = payload.text
        else:
            try:
                text = str(payload["text"])
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Ignoring malformed phone text payload: %s", payload)
                return
        self._latest_text = text

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fit_font_and_wrap(
        self, text: str, window_width: int, window_height: int
    ) -> tuple[int, list[str], int]:
        """Return font size, wrapped lines, and line height that fit *text* on screen."""

        # Iterate from largest to smallest size to find the best fit.
        for size in range(self._font_size_max, self._font_size_min - 1, -1):
            font_candidate = self._get_font(size)

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
                return size, wrapped, font_candidate.get_linesize()

        # If nothing fit, return the smallest size anyway.
        fallback_font = self._get_font(self._font_size_min)
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

        return self._font_size_min, wrapped, fallback_font.get_linesize()

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
        last_text = self._latest_text or "Waiting for text..."

        # Skip rendering if we have nothing to show.
        if not last_text:
            return

        window_width, window_height = window.get_size()

        state = self.state
        # Recalculate font/wrapping if the text or available space changed.
        if (
            last_text != state.cached_text
            or state.window_size != (window_width, window_height)
            or state.font_size is None
        ):
            font_size, wrapped_lines, line_height = self._fit_font_and_wrap(
                last_text, window_width, window_height
            )
            self.update_state(
                cached_text=last_text,
                wrapped_lines=tuple(wrapped_lines),
                window_size=(window_width, window_height),
                font_size=font_size,
                line_height=line_height,
            )
            state = self.state

        # Calculate how many lines can fit in the window height
        font_for_rendering = self._get_font(state.font_size or self._font_size_min)
        line_height = state.line_height or font_for_rendering.get_linesize()
        max_lines_visible = max(1, window_height // line_height)

        # Truncate lines to only show what fits in the window
        visible_lines = list(state.wrapped_lines[:max_lines_visible])

        # Calculate total height of visible lines
        total_height = len(visible_lines) * line_height

        # Calculate vertical centring.
        y = (window_height - total_height) // 2

        # Draw each line centred horizontally.
        for line in visible_lines:
            rendered = font_for_rendering.render(line, True, (255, 105, 180))
            text_width, _ = rendered.get_size()
            x = (window_width - text_width) // 2
            window.blit(rendered, (x, y))
            y += line_height

    def _get_font(self, size: int) -> pygame.font.Font:
        """Return a cached *pygame.font.Font* for ``size``."""

        if size not in self._font_cache:
            self._font_cache[size] = Loader.load_font(
                "Grand9K Pixel.ttf", font_size=size
            )
        return self._font_cache[size]

    def _create_initial_state(self) -> FreeTextRendererState:
        return FreeTextRendererState()
