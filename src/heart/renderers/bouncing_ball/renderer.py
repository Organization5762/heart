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
                                                   DEFAULT_BALL_SPEED)
from heart.renderers.bouncing_ball.state import BouncingBallState
from heart.runtime.display_context import DisplayContext

BACKGROUND_COLOR = (0, 0, 0)
FRAME_COLOR = (34, 48, 58)
FRAME_HIGHLIGHT_COLOR = (70, 92, 108)
STRING_COLOR = (118, 145, 158)
BALL_CORE_COLOR = (76, 242, 255)
BALL_EDGE_COLOR = (255, 76, 216)
BALL_SHADOW_COLOR = (12, 24, 32)
HIGHLIGHT_COLOR = (255, 255, 255)
CRADLE_BALL_COUNT = 5
CRADLE_PERIOD_SECONDS = 2.6
CRADLE_MAX_SWING_RADIANS = 0.92
CRADLE_VIEW_SIDE = "side"
CRADLE_VIEW_FRONT = "front"


class BouncingBallRenderer(StatefulBaseRenderer[BouncingBallState]):
    """Render the legacy bounce slot as a Newton's cradle animation."""

    def __init__(
        self,
        provider: ObservableProvider[BouncingBallState] | None = None,
    ) -> None:
        super().__init__(builder=provider)
        self.device_display_mode = DeviceDisplayMode.FULL
        self._animation_start_s = time.monotonic()

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

        elapsed_s = time.monotonic() - self._animation_start_s
        window.fill(BACKGROUND_COLOR)
        for index, rect in enumerate(
            self._panel_rects(window=window, orientation=orientation)
        ):
            self._draw_clipped_cradle(
                screen=window.screen,
                rect=rect,
                elapsed_s=elapsed_s,
                view=self._panel_view(index),
            )

    def _draw_clipped_cradle(
        self,
        *,
        screen: pygame.Surface,
        rect: pygame.Rect,
        elapsed_s: float,
        view: str,
    ) -> None:
        previous_clip = screen.get_clip()
        screen.set_clip(rect)
        try:
            self._draw_cradle(
                screen=screen,
                rect=rect,
                elapsed_s=elapsed_s,
                view=view,
            )
        finally:
            screen.set_clip(previous_clip)

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
                column * panel_width,
                row * panel_height,
                panel_width,
                panel_height,
            )
            for row in range(rows)
            for column in range(columns)
        ]

    @staticmethod
    def _panel_view(panel_index: int) -> str:
        return CRADLE_VIEW_SIDE if panel_index % 2 == 0 else CRADLE_VIEW_FRONT

    def _draw_cradle(
        self,
        *,
        screen: pygame.Surface,
        rect: pygame.Rect,
        elapsed_s: float,
        view: str,
    ) -> None:
        frame = self._cradle_frame(rect)
        anchor_y = frame.top
        rest_y = frame.bottom - max(5, rect.height // 12)
        string_length = max(8, rest_y - anchor_y)
        radius = self._ball_radius(rect)
        swing_angles = self._swing_angles(elapsed_s)

        pygame.draw.line(screen, FRAME_HIGHLIGHT_COLOR, frame.topleft, frame.topright, 2)
        pygame.draw.line(screen, FRAME_COLOR, frame.bottomleft, frame.topleft, 1)
        pygame.draw.line(screen, FRAME_COLOR, frame.bottomright, frame.topright, 1)

        if view == CRADLE_VIEW_SIDE:
            self._draw_side_view(
                screen=screen,
                rect=rect,
                anchor_y=anchor_y,
                string_length=string_length,
                radius=radius,
                swing_angles=swing_angles,
            )
        else:
            self._draw_front_view(
                screen=screen,
                rect=rect,
                anchor_y=anchor_y,
                string_length=string_length,
                radius=radius,
                swing_angles=swing_angles,
            )

    def _draw_front_view(
        self,
        *,
        screen: pygame.Surface,
        rect: pygame.Rect,
        anchor_y: int,
        string_length: int,
        radius: int,
        swing_angles: tuple[float, ...],
    ) -> None:
        centers = self._rest_centers(rect=rect, radius=radius)
        bob_positions: list[tuple[int, int]] = []
        for index, rest_x in enumerate(centers):
            angle = swing_angles[index]
            anchor = (rest_x, anchor_y)
            bob = (
                rest_x + round(math.sin(angle) * string_length),
                anchor_y + round(math.cos(angle) * string_length),
            )
            bob_positions.append(bob)
            pygame.draw.line(screen, STRING_COLOR, anchor, bob, 1)

        for index, center in enumerate(bob_positions):
            self._draw_cradle_ball(
                screen=screen,
                center=center,
                radius=radius,
                active=abs(swing_angles[index]) > 0.01,
            )

    def _draw_side_view(
        self,
        *,
        screen: pygame.Surface,
        rect: pygame.Rect,
        anchor_y: int,
        string_length: int,
        radius: int,
        swing_angles: tuple[float, ...],
    ) -> None:
        base_x = rect.centerx
        bob_positions: list[tuple[int, int]] = []
        for index in range(CRADLE_BALL_COUNT):
            angle = swing_angles[index]
            anchor = (base_x, anchor_y)
            bob = (
                anchor[0],
                anchor_y + round(math.cos(angle) * string_length),
            )
            bob_positions.append(bob)
            pygame.draw.line(screen, STRING_COLOR, anchor, bob, 1)

        for index, center in sorted(
            enumerate(bob_positions),
            key=lambda item: self._side_view_depth_scale(swing_angles[item[0]]),
        ):
            depth_scale = self._side_view_depth_scale(swing_angles[index])
            scaled_radius = max(2, round(radius * depth_scale))
            self._draw_cradle_ball(
                screen=screen,
                center=center,
                radius=scaled_radius,
                active=abs(swing_angles[index]) > 0.01,
                core_color=BALL_EDGE_COLOR if depth_scale > 1.05 else BALL_CORE_COLOR,
            )

    @staticmethod
    def _cradle_frame(rect: pygame.Rect) -> pygame.Rect:
        margin_x = max(4, rect.width // 20)
        top = rect.top + max(3, rect.height // 8)
        bottom = rect.bottom - max(3, rect.height // 10)
        return pygame.Rect(
            rect.left + margin_x,
            top,
            rect.width - (margin_x * 2),
            bottom - top,
        )

    @staticmethod
    def _ball_radius(rect: pygame.Rect) -> int:
        return max(5, min(rect.height // 5, rect.width // 22))

    @classmethod
    def _rest_centers(cls, *, rect: pygame.Rect, radius: int) -> tuple[int, ...]:
        usable_width = max(1, rect.width - radius * 4)
        spacing = min(radius * 2, usable_width // (CRADLE_BALL_COUNT + 1))
        total_width = spacing * (CRADLE_BALL_COUNT - 1)
        start = rect.centerx - total_width // 2
        return tuple(start + spacing * index for index in range(CRADLE_BALL_COUNT))

    @staticmethod
    def _swing_angles(elapsed_s: float) -> tuple[float, ...]:
        phase = (elapsed_s % CRADLE_PERIOD_SECONDS) / CRADLE_PERIOD_SECONDS
        left_angle = 0.0
        right_angle = 0.0
        if phase < 0.5:
            local = phase / 0.5
            left_angle = -math.sin(local * math.pi) * CRADLE_MAX_SWING_RADIANS
        else:
            local = (phase - 0.5) / 0.5
            right_angle = math.sin(local * math.pi) * CRADLE_MAX_SWING_RADIANS
        return (left_angle, 0.0, 0.0, 0.0, right_angle)

    @staticmethod
    def _side_view_depth_scale(angle: float) -> float:
        return 0.72 + abs(math.sin(angle)) * 1.18

    def _draw_cradle_ball(
        self,
        *,
        screen: pygame.Surface,
        center: tuple[int, int],
        radius: int,
        active: bool,
        core_color: tuple[int, int, int] = BALL_CORE_COLOR,
    ) -> None:
        shadow_center = (center[0] + max(1, radius // 3), center[1] + max(1, radius // 3))
        pygame.draw.circle(screen, BALL_SHADOW_COLOR, shadow_center, radius)
        pygame.draw.circle(screen, core_color, center, radius)
        edge_color = BALL_EDGE_COLOR if active else FRAME_HIGHLIGHT_COLOR
        pygame.draw.circle(screen, edge_color, center, radius, 1)
        highlight_offset = max(1, radius // 3)
        pygame.draw.circle(
            screen,
            HIGHLIGHT_COLOR,
            (center[0] - highlight_offset, center[1] - highlight_offset),
            max(1, radius // 4),
        )
