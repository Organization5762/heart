from __future__ import annotations

from dataclasses import replace

import pygame

from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.cube_pong.renderer import (
    BALL_COLORS,
    PADDLE_ONE_COLOR,
    PADDLE_TWO_COLOR,
    CubePongRenderer,
)
from heart.renderers.cube_pong.state import (
    ROUTE_ACROSS_SCREEN_FOUR,
    ROUTE_ACROSS_SCREEN_TWO,
    CubePongBall,
    CubePongControls,
    CubePongState,
    advance_cube_pong_state,
    new_cube_pong_round,
)
from heart.runtime.display_context import DisplayContext


def test_scores_show_both_player_colors_on_both_player_faces(device: Device) -> None:
    screen_width = 64
    window = _pong_window(device=device, screen_width=screen_width)
    renderer = CubePongRenderer()
    state = _pong_state(player_one_score=12, player_two_score=34)

    renderer._draw_scores(window, state)

    assert _color_count(window.screen, PADDLE_ONE_COLOR, pygame.Rect(0, 0, 64, 64)) > 0
    assert _color_count(window.screen, PADDLE_TWO_COLOR, pygame.Rect(0, 0, 64, 64)) > 0
    assert (
        _color_count(
            window.screen,
            PADDLE_ONE_COLOR,
            pygame.Rect(screen_width * 2, 0, 64, 64),
        )
        > 0
    )
    assert (
        _color_count(
            window.screen,
            PADDLE_TWO_COLOR,
            pygame.Rect(screen_width * 2, 0, 64, 64),
        )
        > 0
    )


def test_ball_draws_over_score_pixels(device: Device) -> None:
    screen_width = 64
    window = _pong_window(device=device, screen_width=screen_width)
    renderer = CubePongRenderer()
    state = _pong_state(player_one_score=8, player_two_score=8)

    renderer._draw_scores(window, state)
    score_pixel = _first_color_pixel(
        window.screen,
        (PADDLE_ONE_COLOR, PADDLE_TWO_COLOR),
        pygame.Rect(0, 0, screen_width, 64),
    )
    assert score_pixel is not None

    renderer._draw(
        window,
        replace(
            state,
            balls=(
                CubePongBall(
                    route_name=ROUTE_ACROSS_SCREEN_TWO,
                    x=score_pixel[0],
                    y=score_pixel[1],
                    vx=0.0,
                    vy=0.0,
                ),
                CubePongBall(
                    route_name=ROUTE_ACROSS_SCREEN_FOUR,
                    x=screen_width * 4,
                    y=0.0,
                    vx=0.0,
                    vy=0.0,
                ),
            ),
        ),
    )

    assert window.screen.get_at(score_pixel)[:3] == BALL_COLORS[0]


def test_second_ball_start_is_staggered() -> None:
    state = new_cube_pong_round(64, 64)

    assert state.balls[0].launch_delay_s == 0
    assert state.balls[1].launch_delay_s > 0

    advanced = advance_cube_pong_state(state, CubePongControls(), 0.05)

    assert advanced.balls[0].x > state.balls[0].x
    assert advanced.balls[1].x == state.balls[1].x
    assert advanced.balls[1].y == state.balls[1].y
    assert advanced.balls[1].launch_delay_s < state.balls[1].launch_delay_s


def test_reset_reinitializes_scores(
    device: Device,
    manager: PeripheralManager,
) -> None:
    renderer = CubePongRenderer()
    window = DisplayContext(
        device=device,
        screen=pygame.Surface((256, 64), pygame.SRCALPHA),
        clock=pygame.time.Clock(),
    )
    renderer.initialize(window, manager, device.orientation)
    renderer.set_state(replace(renderer.state, player_one_score=7, player_two_score=9))

    renderer.reset()

    assert not renderer.initialized
    renderer.initialize(window, manager, device.orientation)
    assert renderer.state.player_one_score == 0
    assert renderer.state.player_two_score == 0


def _pong_state(
    *,
    player_one_score: int,
    player_two_score: int,
) -> CubePongState:
    return CubePongState(
        screen_width=64,
        screen_height=64,
        paddle_one_y=32,
        paddle_two_y=32,
        balls=(
            CubePongBall(
                route_name=ROUTE_ACROSS_SCREEN_TWO,
                x=16,
                y=16,
                vx=0,
                vy=0,
            ),
            CubePongBall(
                route_name=ROUTE_ACROSS_SCREEN_FOUR,
                x=16,
                y=48,
                vx=0,
                vy=0,
            ),
        ),
        player_one_score=player_one_score,
        player_two_score=player_two_score,
    )


def _pong_window(*, device: Device, screen_width: int) -> DisplayContext:
    return DisplayContext(
        device=device,
        screen=pygame.Surface((screen_width * 4, 64), pygame.SRCALPHA),
        clock=pygame.time.Clock(),
    )


def _color_count(
    screen: pygame.Surface | None,
    color: tuple[int, int, int],
    rect: pygame.Rect,
) -> int:
    assert screen is not None
    return sum(
        1
        for y in range(rect.top, rect.bottom)
        for x in range(rect.left, rect.right)
        if screen.get_at((x, y))[:3] == color
    )


def _first_color_pixel(
    screen: pygame.Surface | None,
    colors: tuple[tuple[int, int, int], ...],
    rect: pygame.Rect,
) -> tuple[int, int] | None:
    assert screen is not None
    for y in range(rect.top, rect.bottom):
        for x in range(rect.left, rect.right):
            if screen.get_at((x, y))[:3] in colors:
                return x, y
    return None
