from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class PortholeWindowState:
    elapsed: float


class PortholeWindowRenderer(AtomicBaseRenderer[PortholeWindowState]):
    """Render a brass porthole with a softly animated outdoor scene."""

    def __init__(self) -> None:
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
        return PortholeWindowState(elapsed=0.0)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        elapsed = self.state.elapsed + clock.get_time() / 1000.0
        self.update_state(elapsed=elapsed)
        width, height = window.get_size()
        center = (width // 2, height // 2)
        radius = max(48, int(min(width, height) * 0.42))
        frame_width = max(8, radius // 5)
        inner_radius = max(24, radius - frame_width - max(3, frame_width // 4))

        self._draw_wall(window)
        self._draw_shadow(window, center, radius, frame_width)
        self._draw_frame(window, center, radius, frame_width)

        view_surface = self._build_view_surface(inner_radius * 2, elapsed)
        window.blit(
            view_surface,
            (center[0] - inner_radius, center[1] - inner_radius),
        )

        self._draw_glass_highlights(window, center, inner_radius)
        self._draw_rivets(window, center, radius, frame_width)

    def _draw_wall(self, window: pygame.Surface) -> None:
        wall_color = (222, 210, 191)
        window.fill(wall_color)

    def _draw_shadow(
        self,
        window: pygame.Surface,
        center: tuple[int, int],
        radius: int,
        frame_width: int,
    ) -> None:
        shadow_surface = pygame.Surface(window.get_size(), pygame.SRCALPHA)
        outer_radius = radius + frame_width + 10
        inner_radius = radius + frame_width + 2
        pygame.draw.circle(shadow_surface, (0, 0, 0, 90), center, outer_radius)
        pygame.draw.circle(shadow_surface, (0, 0, 0, 0), center, inner_radius)
        window.blit(shadow_surface, (0, 0))

    def _draw_frame(
        self,
        window: pygame.Surface,
        center: tuple[int, int],
        radius: int,
        frame_width: int,
    ) -> None:
        outer_color = (96, 80, 59)
        mid_color = (138, 117, 88)
        inner_color = (177, 152, 116)
        highlight_color = (214, 189, 151)

        pygame.draw.circle(window, outer_color, center, radius + frame_width)
        pygame.draw.circle(window, mid_color, center, radius + frame_width - 4)
        pygame.draw.circle(window, inner_color, center, radius)
        pygame.draw.circle(
            window,
            highlight_color,
            center,
            radius,
            max(2, frame_width // 3),
        )

    def _build_view_surface(self, diameter: int, elapsed: float) -> pygame.Surface:
        view_surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        self._draw_sky(view_surface)
        self._draw_roof(view_surface)
        self._draw_cityline(view_surface)
        self._draw_clouds(view_surface, elapsed)
        self._mask_circle(view_surface)
        return view_surface

    def _draw_sky(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        sky_top = pygame.Color(135, 179, 224)
        sky_bottom = pygame.Color(202, 225, 245)
        for y in range(height):
            blend = y / max(1, height - 1)
            color = pygame.Color(
                int(sky_top.r + (sky_bottom.r - sky_top.r) * blend),
                int(sky_top.g + (sky_bottom.g - sky_top.g) * blend),
                int(sky_top.b + (sky_bottom.b - sky_top.b) * blend),
            )
            pygame.draw.line(surface, color, (0, y), (width, y))

        horizon_color = (225, 233, 237)
        horizon_y = int(height * 0.58)
        pygame.draw.line(surface, horizon_color, (0, horizon_y), (width, horizon_y), 2)

    def _draw_roof(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        ridge_y = int(height * 0.62)
        eave_y = int(height * 0.88)

        roof_light = (163, 166, 173)
        roof_shadow = (115, 119, 125)

        roof_points = [
            (-int(width * 0.1), eave_y),
            (width + int(width * 0.1), eave_y),
            (int(width * 0.65), height + int(height * 0.12)),
            (int(width * 0.35), height + int(height * 0.12)),
        ]
        pygame.draw.polygon(surface, roof_light, roof_points)

        left_face = [
            (-int(width * 0.1), eave_y),
            (int(width * 0.45), ridge_y),
            (int(width * 0.35), height + int(height * 0.12)),
        ]
        pygame.draw.polygon(surface, roof_shadow, left_face)

        shingle_color = (186, 189, 194)
        for offset in range(0, height - ridge_y, 6):
            y = ridge_y + offset
            pygame.draw.line(surface, shingle_color, (int(width * 0.1), y), (int(width * 0.9), y))

    def _draw_cityline(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        skyline_color = (146, 156, 170)
        base_y = int(height * 0.63)
        pygame.draw.rect(
            surface,
            skyline_color,
            pygame.Rect(0, base_y, width, int(height * 0.08)),
        )

        tower_color = (169, 178, 190)
        tower_width = max(6, width // 16)
        tower_height = int(height * 0.14)
        tower_rect = pygame.Rect(width * 0.75, base_y - tower_height, tower_width, tower_height)
        surface.fill(tower_color, tower_rect)

    def _draw_clouds(self, surface: pygame.Surface, elapsed: float) -> None:
        width, height = surface.get_size()
        cloud_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        cloud_color = (255, 255, 255, 180)
        drift = (math.sin(elapsed * 0.25) + 1) / 2
        offset = int(drift * width * 0.25)
        primary_rect = pygame.Rect(-width // 6 + offset, height * 0.2, width // 2, height // 5)
        secondary_rect = pygame.Rect(width * 0.3 + offset, height * 0.28, width // 3, height // 6)
        pygame.draw.ellipse(cloud_surface, cloud_color, primary_rect)
        pygame.draw.ellipse(cloud_surface, cloud_color, secondary_rect)
        surface.blit(cloud_surface, (0, 0))

    def _mask_circle(self, surface: pygame.Surface) -> None:
        diameter = surface.get_width()
        mask = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.circle(
            mask,
            (255, 255, 255, 255),
            (diameter // 2, diameter // 2),
            diameter // 2,
        )
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    def _draw_glass_highlights(
        self,
        window: pygame.Surface,
        center: tuple[int, int],
        radius: int,
    ) -> None:
        highlight_surface = pygame.Surface(window.get_size(), pygame.SRCALPHA)
        highlight_color = (255, 255, 255, 70)
        rect_size = radius * 2
        rect = pygame.Rect(0, 0, rect_size, rect_size)
        rect.center = center
        pygame.draw.arc(
            highlight_surface,
            highlight_color,
            rect.inflate(-radius // 2, -radius // 2),
            math.radians(200),
            math.radians(320),
            max(2, radius // 12),
        )
        pygame.draw.arc(
            highlight_surface,
            (255, 255, 255, 35),
            rect.inflate(-radius // 3, -radius // 3),
            math.radians(30),
            math.radians(95),
            max(1, radius // 18),
        )
        window.blit(highlight_surface, (0, 0))

    def _draw_rivets(
        self,
        window: pygame.Surface,
        center: tuple[int, int],
        radius: int,
        frame_width: int,
    ) -> None:
        rivet_radius = max(2, frame_width // 4)
        rivet_color = (190, 167, 130)
        rivet_shadow = (79, 66, 48)
        rivet_highlight = (233, 214, 182)
        rivet_ring_radius = radius - frame_width // 2

        for step in range(6):
            angle = math.radians(60 * step)
            x = center[0] + int(math.cos(angle) * rivet_ring_radius)
            y = center[1] + int(math.sin(angle) * rivet_ring_radius)
            pygame.draw.circle(window, rivet_shadow, (x + 1, y + 1), rivet_radius)
            pygame.draw.circle(window, rivet_color, (x, y), rivet_radius)
            pygame.draw.circle(
                window,
                rivet_highlight,
                (x - 1, y - 1),
                max(1, rivet_radius - 1),
            )
