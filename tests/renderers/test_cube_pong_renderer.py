from __future__ import annotations

import pygame

from heart.device import Cube
from heart.device.local.device import LocalScreen
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.cube_pong.renderer import (PADDLE_ONE_COLOR,
                                                PADDLE_TWO_COLOR,
                                                CubePongRenderer)
from heart.renderers.cube_pong.state import (
    PLAYER_ONE, PLAYER_TWO, ROUTE_ACROSS_SCREEN_FOUR, CubePongBall,
    CubePongControls, CubePongState, advance_cube_pong_state, base_ball_speed,
    face_position_for_ball, new_cube_pong_round, paddle_path_x,
    paddle_size)
from heart.runtime.display_context import DisplayContext


class _Clock:
    def __init__(self, elapsed_ms: int) -> None:
        self._elapsed_ms = elapsed_ms

    def get_time(self) -> int:
        return self._elapsed_ms


def test_new_round_starts_two_synchronized_opposite_balls() -> None:
    state = new_cube_pong_round(64, 64)

    assert len(state.balls) == 2
    assert state.balls[0].vx == -state.balls[1].vx
    assert state.balls[0].vx == base_ball_speed(64)
    assert state.balls[0].x < state.balls[1].x


def test_screen_four_route_maps_middle_segment_to_fourth_face() -> None:
    ball = CubePongBall(
        route_name=ROUTE_ACROSS_SCREEN_FOUR,
        x=96,
        y=20,
        vx=1,
        vy=0,
    )

    position = face_position_for_ball(ball, 64)

    assert position is not None
    assert position.face_index == 3
    assert position.x == 32
    assert position.y == 20


def test_ball_bounces_when_it_reaches_center_paddle() -> None:
    screen_width = 64
    screen_height = 64
    _, paddle_two_x = paddle_path_x(screen_width)
    paddle_width, _ = paddle_size(screen_width, screen_height)
    state = CubePongState(
        screen_width=screen_width,
        screen_height=screen_height,
        paddle_one_y=screen_height / 2,
        paddle_two_y=screen_height / 2,
        balls=(
            CubePongBall(
                route_name="screens_1_2_3",
                x=paddle_two_x - paddle_width - 4,
                y=screen_height / 2,
                vx=base_ball_speed(screen_width),
                vy=0,
            ),
            new_cube_pong_round(screen_width, screen_height).balls[1],
        ),
    )

    next_state = advance_cube_pong_state(state, CubePongControls(), 0.1)

    assert next_state.losing_player is None
    assert next_state.balls[0].vx < 0


def test_ball_miss_flags_losing_player_then_resets_round() -> None:
    screen_width = 64
    screen_height = 64
    _, paddle_two_x = paddle_path_x(screen_width)
    state = CubePongState(
        screen_width=screen_width,
        screen_height=screen_height,
        paddle_one_y=screen_height / 2,
        paddle_two_y=screen_height * 0.1,
        balls=(
            CubePongBall(
                route_name="screens_1_2_3",
                x=paddle_two_x + 10,
                y=screen_height * 0.9,
                vx=base_ball_speed(screen_width),
                vy=0,
            ),
            new_cube_pong_round(screen_width, screen_height).balls[1],
        ),
    )

    lost_state = advance_cube_pong_state(state, CubePongControls(), 0.1)
    reset_state = lost_state
    for _ in range(25):
        reset_state = advance_cube_pong_state(reset_state, CubePongControls(), 0.05)

    assert lost_state.losing_player == PLAYER_TWO
    assert lost_state.player_one_score == 1
    assert lost_state.player_two_score == 0
    assert reset_state.losing_player is None
    assert reset_state.player_one_score == 1
    assert reset_state.player_two_score == 0
    assert reset_state.balls[0].vx > 0


def test_player_two_scores_when_player_one_misses() -> None:
    screen_width = 64
    screen_height = 64
    paddle_one_x, _ = paddle_path_x(screen_width)
    state = CubePongState(
        screen_width=screen_width,
        screen_height=screen_height,
        paddle_one_y=screen_height * 0.1,
        paddle_two_y=screen_height / 2,
        balls=(
            CubePongBall(
                route_name="screens_1_2_3",
                x=paddle_one_x - 10,
                y=screen_height * 0.9,
                vx=-base_ball_speed(screen_width),
                vy=0,
            ),
            new_cube_pong_round(screen_width, screen_height).balls[1],
        ),
    )

    lost_state = advance_cube_pong_state(state, CubePongControls(), 0.1)

    assert lost_state.losing_player == PLAYER_ONE
    assert lost_state.player_one_score == 0
    assert lost_state.player_two_score == 1


def test_renderer_draws_on_all_cube_sides() -> None:
    pygame.init()
    orientation = Cube.sides()
    display = DisplayContext(
        device=LocalScreen(orientation=orientation, width=64, height=64),
        screen=pygame.Surface((256, 64), pygame.SRCALPHA),
        clock=_Clock(16),
        can_configure_display=False,
    )
    renderer = CubePongRenderer()

    renderer.initialize(display, PeripheralManager(), orientation)
    renderer.real_process(display, orientation)

    assert display.screen is not None
    sampled_columns = [
        display.screen.get_at((face_index * 64 + 32, 32))[:3]
        for face_index in range(4)
    ]
    assert any(color != (4, 5, 8) for color in sampled_columns)


def test_renderer_draws_scores_with_matching_paddle_colors() -> None:
    pygame.init()
    display = DisplayContext(
        device=LocalScreen(orientation=Cube.sides(), width=64, height=64),
        screen=pygame.Surface((256, 64), pygame.SRCALPHA),
        clock=_Clock(16),
        can_configure_display=False,
    )
    renderer = CubePongRenderer()
    state = CubePongState(
        screen_width=64,
        screen_height=64,
        paddle_one_y=32,
        paddle_two_y=32,
        balls=new_cube_pong_round(64, 64).balls,
        player_one_score=3,
        player_two_score=7,
    )

    assert display.screen is not None
    display.screen.fill((0, 0, 0))
    renderer._draw_scores(display, state)

    left_face_pixels = [
        display.screen.get_at((x, y))[:3]
        for x in range(0, 64)
        for y in range(0, 24)
    ]
    right_face_pixels = [
        display.screen.get_at((x, y))[:3]
        for x in range(128, 192)
        for y in range(0, 24)
    ]
    assert PADDLE_ONE_COLOR in left_face_pixels
    assert PADDLE_TWO_COLOR in right_face_pixels
