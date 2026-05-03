from __future__ import annotations

from math import atan2, hypot, pi
from typing import Any

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.renderers import StatefulBaseRenderer
from heart.renderers.flowtoy_spectrum.provider import (
    DEFAULT_FLOWTOY_RENDER_PERIOD_SECONDS, FlowToySpectrumStateProvider)
from heart.renderers.flowtoy_spectrum.state import (FlowToySpectrumState,
                                                    FlowToySpectrumStop)

DEFAULT_BACKGROUND_COLOR = Color(8, 8, 12)
DEFAULT_DISC_FILL_RATIO = 0.46
DEFAULT_DISC_INNER_RATIO = 0.18


class FlowToySpectrumRenderer(StatefulBaseRenderer[FlowToySpectrumState]):
    def __init__(
        self,
        provider: FlowToySpectrumStateProvider | None = None,
    ) -> None:
        self.provider = provider or FlowToySpectrumStateProvider()
        super().__init__(builder=self.provider)
        self.device_display_mode = DeviceDisplayMode.FULL

    def real_process(
        self,
        window: Any,
        orientation: Orientation,
    ) -> None:
        screen = self._resolve_surface(window)
        width, height = screen.get_size()
        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        outer_radius = max(1.0, min(width, height) * DEFAULT_DISC_FILL_RATIO)
        inner_radius = outer_radius * DEFAULT_DISC_INNER_RATIO
        background = DEFAULT_BACKGROUND_COLOR._as_tuple()
        screen.fill(background)

        group_phase_offset = (self.state.group_id % 360) / 360.0
        animated_phase = (
            self.state.elapsed_s / DEFAULT_FLOWTOY_RENDER_PERIOD_SECONDS
        ) + group_phase_offset

        for x in range(width):
            dx = x - center_x
            for y in range(height):
                dy = y - center_y
                radius = hypot(dx, dy)
                if radius > outer_radius:
                    continue

                angle = atan2(dy, dx)
                normalized_t = ((angle / (2.0 * pi)) + animated_phase) % 1.0
                color = self._interpolate_spectrum(self.state.color_spectrum, normalized_t)
                if radius < inner_radius:
                    blend = radius / max(inner_radius, 1.0)
                    color = self._mix_colors(color, Color(255, 255, 255), blend * 0.2)
                screen.set_at((x, y), color._as_tuple())

    def _resolve_surface(self, window: Any) -> pygame.Surface:
        screen = getattr(window, "screen", None)
        if isinstance(screen, pygame.Surface):
            return screen
        if isinstance(window, pygame.Surface):
            return window
        raise RuntimeError("FlowToySpectrumRenderer requires a pygame surface")

    def _interpolate_spectrum(
        self,
        spectrum: tuple[FlowToySpectrumStop, ...],
        normalized_t: float,
    ) -> Color:
        if not spectrum:
            return DEFAULT_BACKGROUND_COLOR

        clamped_t = normalized_t % 1.0
        previous = spectrum[0]
        for current in spectrum[1:]:
            if clamped_t <= current.t:
                return self._interpolate_between(previous, current, clamped_t)
            previous = current

        wrapped = FlowToySpectrumStop(t=1.0, hex=spectrum[0].hex)
        return self._interpolate_between(previous, wrapped, clamped_t)

    def _interpolate_between(
        self,
        start: FlowToySpectrumStop,
        end: FlowToySpectrumStop,
        t: float,
    ) -> Color:
        start_color = self._hex_to_color(start.hex)
        end_color = self._hex_to_color(end.hex)
        span = max(end.t - start.t, 1e-9)
        ratio = min(1.0, max(0.0, (t - start.t) / span))
        return self._mix_colors(start_color, end_color, ratio)

    def _hex_to_color(self, value: str) -> Color:
        cleaned = value.strip().removeprefix("#")
        if len(cleaned) != 6:
            return DEFAULT_BACKGROUND_COLOR
        return Color(
            r=int(cleaned[0:2], 16),
            g=int(cleaned[2:4], 16),
            b=int(cleaned[4:6], 16),
        )

    def _mix_colors(
        self,
        start: Color,
        end: Color,
        ratio: float,
    ) -> Color:
        clamped_ratio = min(1.0, max(0.0, ratio))
        inverse_ratio = 1.0 - clamped_ratio
        return Color(
            r=int(round((start.r * inverse_ratio) + (end.r * clamped_ratio))),
            g=int(round((start.g * inverse_ratio) + (end.g * clamped_ratio))),
            b=int(round((start.b * inverse_ratio) + (end.b * clamped_ratio))),
        )
