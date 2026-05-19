from __future__ import annotations

import math
import time

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers import StatefulBaseRenderer
from heart.renderers.bouncing_ball.physics import (DEFAULT_BALL_POSITION,
                                                   DEFAULT_BALL_SPEED,
                                                   DEFAULT_MAX_STEP_SECONDS,
                                                   WORLD_LIMIT,
                                                   advance_bouncing_ball_state)
from heart.renderers.bouncing_ball.state import (BallPosition,
                                                 BouncingBallState, ChildBall)
from heart.runtime.display_context import DisplayContext

BACKGROUND_COLOR = (0, 0, 0)
GRID_COLOR = (8, 14, 20)
WALL_COLOR = (28, 38, 48)
ADJACENT_PANEL_COLOR = (5, 10, 15)
ADJACENT_PANEL_EDGE_COLOR = (18, 30, 42)
BALL_CORE_COLOR = (76, 242, 255)
BALL_EDGE_COLOR = (255, 76, 216)
CHILD_BALL_CORE_COLOR = (255, 206, 76)
CHILD_BALL_EDGE_COLOR = (255, 116, 54)
HIGHLIGHT_COLOR = (255, 255, 255)


class BouncingBallRenderer(StatefulBaseRenderer[BouncingBallState]):
    """Render one shared 3D ball from each side of the four-screen cube."""

    def __init__(
        self,
        provider: ObservableProvider[BouncingBallState] | None = None,
    ) -> None:
        super().__init__(builder=provider)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> BouncingBallState:
        del window, peripheral_manager, orientation
        return BouncingBallState(
            position=DEFAULT_BALL_POSITION,
            velocity=DEFAULT_BALL_SPEED,
            last_time_s=time.monotonic(),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if window.screen is None:
            return

        if self.builder is None:
            now_s = time.monotonic()
            dt = min(max(now_s - self.state.last_time_s, 0.0), DEFAULT_MAX_STEP_SECONDS)
            state = advance_bouncing_ball_state(self.state, dt=dt, now_s=now_s)
            self.set_state(state)
        else:
            state = self.state

        window.fill(BACKGROUND_COLOR)
        panel_rects = self._panel_rects(window=window, orientation=orientation)
        for index, rect in enumerate(panel_rects):
            self._draw_panel(
                screen=window.screen,
                rect=rect,
                position=state.position,
                trail=state.trail,
                child_balls=state.child_balls,
                side_index=index,
            )

    def _panel_rects(
        self,
        *,
        window: DisplayContext,
        orientation: Orientation,
    ) -> list[pygame.Rect]:
        columns = max(1, orientation.layout.columns)
        rows = max(1, orientation.layout.rows)
        panel_width = window.get_width() // columns
        panel_height = window.get_height() // rows
        return [
            pygame.Rect(
                col * panel_width,
                row * panel_height,
                panel_width,
                panel_height,
            )
            for row in range(rows)
            for col in range(columns)
        ]

    def _draw_panel(
        self,
        *,
        screen: pygame.Surface,
        rect: pygame.Rect,
        position: BallPosition,
        trail: tuple[BallPosition, ...],
        child_balls: tuple[ChildBall, ...],
        side_index: int,
    ) -> None:
        pygame.draw.rect(screen, BACKGROUND_COLOR, rect)
        self._draw_room(
            screen=screen,
            rect=rect,
            position=position,
            side_index=side_index,
        )
        for child in child_balls:
            age_ratio = child.age_s / max(child.lifetime_s, 1e-9)
            self._draw_ball(
                screen=screen,
                rect=rect,
                position=child.position,
                side_index=side_index,
                alpha=max(0.0, 1.0 - age_ratio),
                radius_scale=child.radius_scale,
                core_color=CHILD_BALL_CORE_COLOR,
                edge_color=CHILD_BALL_EDGE_COLOR,
            )
        for index, trail_position in reversed(list(enumerate(trail))):
            alpha = 1.0 - ((index + 1) / (len(trail) + 1))
            self._draw_ball(
                screen=screen,
                rect=rect,
                position=trail_position,
                side_index=side_index,
                alpha=alpha * 0.32,
                radius_scale=1.0,
                core_color=BALL_CORE_COLOR,
                edge_color=BALL_EDGE_COLOR,
            )
        self._draw_ball(
            screen=screen,
            rect=rect,
            position=position,
            side_index=side_index,
            alpha=1.0,
            radius_scale=1.0,
            core_color=BALL_CORE_COLOR,
            edge_color=BALL_EDGE_COLOR,
        )
        pygame.draw.rect(screen, WALL_COLOR, rect, 1)

    def _draw_room(
        self,
        *,
        screen: pygame.Surface,
        rect: pygame.Rect,
        position: BallPosition,
        side_index: int,
    ) -> None:
        lateral = self._face_lateral(position=position, side_index=side_index)
        vanishing_point = self._precipice_point(rect=rect, lateral=lateral)
        adjacent_panel = self._adjacent_panel_polygon(rect=rect, lateral=lateral)
        inset_x = max(3, rect.width // 9)
        ceiling_y = rect.top + max(3, rect.height // 9)
        floor_y = rect.bottom - max(3, rect.height // 9)
        pygame.draw.polygon(screen, ADJACENT_PANEL_COLOR, adjacent_panel)
        pygame.draw.polygon(screen, ADJACENT_PANEL_EDGE_COLOR, adjacent_panel, 1)
        pygame.draw.line(screen, WALL_COLOR, (rect.left, ceiling_y), (rect.right, ceiling_y))
        pygame.draw.line(screen, WALL_COLOR, (rect.left, floor_y), (rect.right, floor_y))
        for start, end in self._runway_segments(rect=rect, lateral=lateral):
            pygame.draw.line(screen, GRID_COLOR, start, end)
        pygame.draw.line(screen, WALL_COLOR, (rect.left + inset_x, floor_y), vanishing_point)
        pygame.draw.line(screen, WALL_COLOR, (rect.right - inset_x, floor_y), vanishing_point)
        pygame.draw.line(screen, GRID_COLOR, (rect.left + inset_x, ceiling_y), vanishing_point)
        pygame.draw.line(screen, GRID_COLOR, (rect.right - inset_x, ceiling_y), vanishing_point)

    def _draw_ball(
        self,
        *,
        screen: pygame.Surface,
        rect: pygame.Rect,
        position: BallPosition,
        side_index: int,
        alpha: float,
        radius_scale: float,
        core_color: tuple[int, int, int],
        edge_color: tuple[int, int, int],
    ) -> None:
        projected_x, projected_y, radius, near_ratio = self._project_ball(
            rect=rect,
            position=position,
            side_index=side_index,
        )
        radius = int(max(1.0, radius * radius_scale))
        if radius <= 0:
            return

        color = self._depth_color(
            near_ratio=near_ratio,
            alpha=alpha,
            core_color=core_color,
        )
        pygame.draw.circle(screen, color, (projected_x, projected_y), radius)
        if alpha >= 0.95:
            edge = self._scale_color(edge_color, 0.5 + near_ratio * 0.5)
            pygame.draw.circle(screen, edge, (projected_x, projected_y), radius, 1)
            highlight_radius = max(1, radius // 4)
            highlight_offset = max(1, radius // 3)
            pygame.draw.circle(
                screen,
                HIGHLIGHT_COLOR,
                (projected_x - highlight_offset, projected_y - highlight_offset),
                highlight_radius,
            )

    def _project_ball(
        self,
        *,
        rect: pygame.Rect,
        position: BallPosition,
        side_index: int,
    ) -> tuple[int, int, int, float]:
        angle = side_index * math.pi / 2.0
        normal_x = math.sin(angle)
        normal_z = -math.cos(angle)

        lateral = self._face_lateral(position=position, side_index=side_index)
        forward = (position.x * normal_x) + (position.z * normal_z)
        near_ratio = max(0.0, min(1.0, (forward + WORLD_LIMIT) / (WORLD_LIMIT * 2.0)))

        perspective = 0.72 + near_ratio * 0.5
        radius = int(max(2.0, rect.height * (0.08 + near_ratio * 0.16)))
        vanishing_x, vanishing_y = self._precipice_point(rect=rect, lateral=lateral)
        projected_x = rect.centerx + int(lateral * rect.width * 0.24 * perspective)
        projected_y = rect.centery - int(position.y * rect.height * 0.38 * perspective)
        depth_weight = 0.32 + (near_ratio * 0.68)
        x = int((vanishing_x * (1.0 - depth_weight)) + (projected_x * depth_weight))
        y = int((vanishing_y * (1.0 - depth_weight)) + (projected_y * depth_weight))
        x = max(rect.left + radius, min(rect.right - radius - 1, x))
        y = max(rect.top + radius, min(rect.bottom - radius - 1, y))
        return x, y, radius, near_ratio

    @staticmethod
    def _precipice_point(*, rect: pygame.Rect, lateral: float) -> tuple[int, int]:
        x = rect.right - 1 if lateral >= 0.0 else rect.left
        return (x, rect.centery)

    @staticmethod
    def _adjacent_panel_polygon(
        *,
        rect: pygame.Rect,
        lateral: float,
    ) -> tuple[tuple[int, int], ...]:
        edge_x = rect.right - 1 if lateral >= 0.0 else rect.left
        inset_direction = -1 if lateral >= 0.0 else 1
        depth = max(6, rect.width // 4)
        top_y = rect.top + max(3, rect.height // 9)
        bottom_y = rect.bottom - max(3, rect.height // 9)
        far_top_y = rect.top + max(2, rect.height // 4)
        far_bottom_y = rect.bottom - max(2, rect.height // 4)
        far_x = edge_x + (inset_direction * depth)
        return (
            (edge_x, top_y),
            (edge_x, bottom_y),
            (far_x, far_bottom_y),
            (far_x, far_top_y),
        )

    @classmethod
    def _runway_segments(
        cls,
        *,
        rect: pygame.Rect,
        lateral: float,
    ) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
        vanishing_point = cls._precipice_point(rect=rect, lateral=lateral)
        ceiling_y = rect.top + max(3, rect.height // 9)
        floor_y = rect.bottom - max(3, rect.height // 9)
        near_left = (rect.left, floor_y)
        near_right = (rect.right - 1, floor_y)
        far_left = (rect.left, ceiling_y)
        far_right = (rect.right - 1, ceiling_y)
        diagonal = math.hypot(rect.width, rect.height)
        stripe_count = max(3, min(7, int(diagonal // 18)))
        segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for index in range(1, stripe_count + 1):
            t = (index / (stripe_count + 1)) ** 1.45
            left_floor = cls._interpolate_point(near_left, vanishing_point, t)
            right_floor = cls._interpolate_point(near_right, vanishing_point, t)
            left_ceiling = cls._interpolate_point(far_left, vanishing_point, t)
            right_ceiling = cls._interpolate_point(far_right, vanishing_point, t)
            segments.append((left_floor, right_floor))
            segments.append((left_ceiling, right_ceiling))
        return tuple(segments)

    @staticmethod
    def _face_lateral(*, position: BallPosition, side_index: int) -> float:
        angle = side_index * math.pi / 2.0
        tangent_x = math.cos(angle)
        tangent_z = math.sin(angle)
        return (position.x * tangent_x) + (position.z * tangent_z)

    @staticmethod
    def _interpolate_point(
        start: tuple[int, int],
        end: tuple[int, int],
        t: float,
    ) -> tuple[int, int]:
        return (
            int(start[0] + ((end[0] - start[0]) * t)),
            int(start[1] + ((end[1] - start[1]) * t)),
        )

    def _depth_color(
        self,
        *,
        near_ratio: float,
        alpha: float,
        core_color: tuple[int, int, int],
    ) -> tuple[int, int, int]:
        warmth = 0.48 + near_ratio * 0.52
        fade = max(0.0, min(1.0, alpha))
        return self._scale_color(core_color, warmth * fade)

    def _scale_color(
        self,
        color: tuple[int, int, int],
        scale: float,
    ) -> tuple[int, int, int]:
        return tuple(int(max(0, min(255, channel * scale))) for channel in color)
