from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.input import GamepadAxis, GamepadSnapshot
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.cube_pong.state import (
    PLAYER_ONE, CubePongControls, CubePongState, advance_cube_pong_state,
    ball_radius, face_position_for_ball, new_cube_pong_round, paddle_path_x,
    paddle_size)
from heart.runtime.display_context import DisplayContext

BACKGROUND_COLOR = (4, 5, 8)
SEAM_COLOR = (32, 38, 48)
CENTER_MARK_COLOR = (24, 31, 39)
PADDLE_ONE_COLOR = (69, 214, 255)
PADDLE_TWO_COLOR = (255, 105, 160)
BALL_COLORS = ((250, 245, 128), (139, 255, 180))
LOSS_FLASH_COLOR = (105, 10, 24)
KEYBOARD_CONTROL_STEP = 1.0
GAMEPAD_DEAD_ZONE = 0.15


class CubePongRenderer(StatefulBaseRenderer[CubePongState]):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self._peripheral_manager: PeripheralManager | None = None

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> CubePongState:
        self._peripheral_manager = peripheral_manager
        screen_width, screen_height = self._individual_screen_size(window, orientation)
        return new_cube_pong_round(screen_width, screen_height)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        if window.screen is None:
            raise RuntimeError("CubePongRenderer requires an initialized display")
        controls = self._read_controls()
        state = advance_cube_pong_state(self.state, controls, self._delta_s(window))
        self.set_state(state)
        self._draw(window, state)

    def _draw(self, window: DisplayContext, state: CubePongState) -> None:
        window.fill(BACKGROUND_COLOR)
        self._draw_face_guides(window, state)
        if state.losing_player is not None:
            self._draw_loss_flash(window, state)
        self._draw_paddles(window, state)
        self._draw_balls(window, state)

    def _draw_face_guides(self, window: DisplayContext, state: CubePongState) -> None:
        if window.screen is None:
            raise RuntimeError("CubePongRenderer requires an initialized display")
        screen = window.screen
        for face_index in range(1, 4):
            x = face_index * state.screen_width
            pygame.draw.line(
                screen,
                SEAM_COLOR,
                (x, 0),
                (x, state.screen_height),
                width=1,
            )
        for face_index in (1, 3):
            left = face_index * state.screen_width
            pygame.draw.line(
                screen,
                CENTER_MARK_COLOR,
                (left, state.screen_height // 2),
                (left + state.screen_width, state.screen_height // 2),
                width=1,
            )

    def _draw_loss_flash(self, window: DisplayContext, state: CubePongState) -> None:
        if window.screen is None:
            raise RuntimeError("CubePongRenderer requires an initialized display")
        screen = window.screen
        face_index = 0 if state.losing_player == PLAYER_ONE else 2
        rect = pygame.Rect(
            face_index * state.screen_width,
            0,
            state.screen_width,
            state.screen_height,
        )
        pygame.draw.rect(screen, LOSS_FLASH_COLOR, rect)

    def _draw_paddles(self, window: DisplayContext, state: CubePongState) -> None:
        paddle_width, paddle_height = paddle_size(
            state.screen_width, state.screen_height
        )
        paddle_one_path_x, paddle_two_path_x = paddle_path_x(state.screen_width)
        paddle_one_x = paddle_one_path_x - (paddle_width / 2)
        paddle_two_x = paddle_two_path_x - (paddle_width / 2)
        self._draw_paddle(
            window,
            x=round(paddle_one_x),
            y=round(state.paddle_one_y - paddle_height / 2),
            width=paddle_width,
            height=paddle_height,
            color=PADDLE_ONE_COLOR,
        )
        self._draw_paddle(
            window,
            x=round(paddle_two_x),
            y=round(state.paddle_two_y - paddle_height / 2),
            width=paddle_width,
            height=paddle_height,
            color=PADDLE_TWO_COLOR,
        )

    def _draw_paddle(
        self,
        window: DisplayContext,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple[int, int, int],
    ) -> None:
        if window.screen is None:
            raise RuntimeError("CubePongRenderer requires an initialized display")
        screen = window.screen
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, color, rect)

    def _draw_balls(self, window: DisplayContext, state: CubePongState) -> None:
        if window.screen is None:
            raise RuntimeError("CubePongRenderer requires an initialized display")
        screen = window.screen
        radius = ball_radius(state.screen_width)
        for index, ball in enumerate(state.balls):
            position = face_position_for_ball(ball, state.screen_width)
            if position is None:
                continue
            center = (
                round(position.face_index * state.screen_width + position.x),
                round(position.y),
            )
            pygame.draw.circle(screen, BALL_COLORS[index], center, radius)

    def _read_controls(self) -> CubePongControls:
        pad_one = 0.0
        pad_two = 0.0
        if self._peripheral_manager is not None:
            snapshots = self._peripheral_manager.gamepad_controller.snapshots(
                consume_taps=False
            )
            connected = tuple(snapshot for snapshot in snapshots if snapshot.connected)
            if len(connected) >= 2:
                pad_one = self._left_control(connected[0])
                pad_two = self._left_control(connected[1])
            elif len(connected) == 1:
                pad_one = self._left_control(connected[0])
                pad_two = self._right_control(connected[0])

        keyboard_one, keyboard_two = self._keyboard_controls()
        return CubePongControls(
            player_one=keyboard_one if keyboard_one != 0 else pad_one,
            player_two=keyboard_two if keyboard_two != 0 else pad_two,
        )

    def _left_control(self, snapshot: GamepadSnapshot) -> float:
        axis = snapshot.axis_value(GamepadAxis.LEFT_Y, dead_zone=GAMEPAD_DEAD_ZONE)
        if axis != 0:
            return axis
        return -float(snapshot.dpad.y)

    def _right_control(self, snapshot: GamepadSnapshot) -> float:
        return snapshot.axis_value(GamepadAxis.RIGHT_Y, dead_zone=GAMEPAD_DEAD_ZONE)

    def _keyboard_controls(self) -> tuple[float, float]:
        try:
            pygame.event.pump()
            keys = pygame.key.get_pressed()
        except pygame.error:
            return 0.0, 0.0

        player_one = 0.0
        player_two = 0.0
        if keys[pygame.K_w]:
            player_one -= KEYBOARD_CONTROL_STEP
        if keys[pygame.K_s]:
            player_one += KEYBOARD_CONTROL_STEP
        if keys[pygame.K_UP]:
            player_two -= KEYBOARD_CONTROL_STEP
        if keys[pygame.K_DOWN]:
            player_two += KEYBOARD_CONTROL_STEP
        return player_one, player_two

    def _delta_s(self, window: DisplayContext) -> float:
        if window.clock is None:
            return 1 / 60
        elapsed_ms = window.clock.get_time()
        if elapsed_ms <= 0:
            return 1 / 60
        return elapsed_ms / 1000

    def _individual_screen_size(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> tuple[int, int]:
        width, height = window.get_size()
        columns = max(1, orientation.layout.columns)
        rows = max(1, orientation.layout.rows)
        return max(1, width // columns), max(1, height // rows)
