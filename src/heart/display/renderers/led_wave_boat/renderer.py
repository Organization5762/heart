from __future__ import annotations

import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import StatefulBaseRenderer
from heart.display.renderers.led_wave_boat.provider import \
    LedWaveBoatStateProvider
from heart.display.renderers.led_wave_boat.state import (LedWaveBoatState,
                                                         SprayParticle, clamp)


class LedWaveBoat(StatefulBaseRenderer[LedWaveBoatState]):
    """Render sinusoidal water motion driven by accelerometer input."""

    def __init__(self, builder: LedWaveBoatStateProvider) -> None:
        super().__init__(builder=builder)
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    @staticmethod
    def _draw_water_column(
        screen: Surface,
        column: int,
        crest_y: int,
        screen_height: int,
        crest_color: tuple[int, int, int],
        body_color: tuple[int, int, int],
    ) -> None:
        pygame.draw.line(screen, body_color, (column, crest_y), (column, screen_height - 1))
        screen.set_at((column, crest_y), crest_color)

    @staticmethod
    def _draw_boat(screen: Surface, x: float, y: float, sway: float) -> None:
        sail_offset = int(round(sway))
        px = int(round(x))
        py = int(round(y))

        hull_color = (120, 78, 48)
        deck_color = (170, 120, 90)
        mast_color = (90, 66, 42)
        sail_color = (235, 240, 255)
        sail_shadow = (180, 200, 255)

        sprite = (
            (-2, 1, hull_color),
            (-1, 1, hull_color),
            (0, 1, hull_color),
            (1, 1, hull_color),
            (-1, 0, deck_color),
            (0, 0, deck_color),
            (0, -1, mast_color),
            (0, -2, mast_color),
            (1, -2 + sail_offset, sail_color),
            (2, -2 + sail_offset, sail_color),
            (1, -3 + sail_offset, sail_shadow),
        )

        width, height = screen.get_size()
        for dx, dy, color in sprite:
            sx = px + dx
            sy = py + dy
            if 0 <= sx < width and 0 <= sy < height:
                screen.set_at((sx, sy), color)

    @staticmethod
    def _draw_particles(screen: Surface, particles: list[SprayParticle]) -> None:
        spray_color = (190, 220, 255)
        width, height = screen.get_size()
        for particle in particles:
            sx = int(round(particle.x))
            sy = int(round(particle.y))
            if 0 <= sx < width and 0 <= sy < height:
                screen.set_at((sx, sy), spray_color)

    def real_process(
        self,
        window: Surface,
        clock: Clock,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        if width == 0 or height == 0 or not self.state.heights:
            return

        window.fill((5, 8, 20))

        foam_color = (185, 220, 255)
        water_color = (20, 80, 150)
        deep_color = (10, 30, 70)

        for x, crest in enumerate(self.state.heights):
            crest_px = int(clamp(round(crest), 0, height - 1))
            slope = crest - self.state.heights[x - 1 if x > 0 else -1]
            crest_mix = clamp(abs(slope) * 0.6, 0.0, 1.0)
            crest_color = (
                int(foam_color[0] * crest_mix + water_color[0] * (1 - crest_mix)),
                int(foam_color[1] * crest_mix + water_color[1] * (1 - crest_mix)),
                int(foam_color[2] * crest_mix + water_color[2] * (1 - crest_mix)),
            )
            if crest_px < height - 1:
                self._draw_water_column(
                    window,
                    column=x,
                    crest_y=crest_px,
                    screen_height=height,
                    crest_color=crest_color,
                    body_color=deep_color,
                )
            else:
                window.set_at((x, crest_px), crest_color)

        self._draw_particles(window, self.state.particles)
        self._draw_boat(window, self.state.boat_x, self.state.boat_y, self.state.sway)
