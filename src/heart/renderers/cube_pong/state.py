from __future__ import annotations

from dataclasses import dataclass

PLAYER_ONE = 1
PLAYER_TWO = 2
ROUTE_ACROSS_SCREEN_TWO = "screens_1_2_3"
ROUTE_ACROSS_SCREEN_FOUR = "screens_1_4_3"
ROUND_RESET_HOLD_S = 1.0


@dataclass(frozen=True, slots=True)
class CubePongRoute:
    name: str
    faces: tuple[int, int, int]
    start_player: int
    end_player: int


@dataclass(frozen=True, slots=True)
class CubePongBall:
    route_name: str
    x: float
    y: float
    vx: float
    vy: float


@dataclass(frozen=True, slots=True)
class CubePongControls:
    player_one: float = 0.0
    player_two: float = 0.0


@dataclass(frozen=True, slots=True)
class CubePongState:
    screen_width: int
    screen_height: int
    paddle_one_y: float
    paddle_two_y: float
    balls: tuple[CubePongBall, CubePongBall]
    player_one_score: int = 0
    player_two_score: int = 0
    losing_player: int | None = None
    reset_remaining_s: float = 0.0


@dataclass(frozen=True, slots=True)
class FacePosition:
    face_index: int
    x: float
    y: float


ROUTES = {
    ROUTE_ACROSS_SCREEN_TWO: CubePongRoute(
        name=ROUTE_ACROSS_SCREEN_TWO,
        faces=(0, 1, 2),
        start_player=PLAYER_ONE,
        end_player=PLAYER_TWO,
    ),
    ROUTE_ACROSS_SCREEN_FOUR: CubePongRoute(
        name=ROUTE_ACROSS_SCREEN_FOUR,
        faces=(2, 3, 0),
        start_player=PLAYER_TWO,
        end_player=PLAYER_ONE,
    ),
}


def new_cube_pong_round(screen_width: int, screen_height: int) -> CubePongState:
    return _new_cube_pong_round(
        screen_width,
        screen_height,
        player_one_score=0,
        player_two_score=0,
    )


def _new_cube_pong_round(
    screen_width: int,
    screen_height: int,
    *,
    player_one_score: int,
    player_two_score: int,
) -> CubePongState:
    paddle_one_x, paddle_two_x = paddle_path_x(screen_width)
    radius = ball_radius(screen_width)
    paddle_width, _ = paddle_size(screen_width, screen_height)
    ball_speed = base_ball_speed(screen_width)
    vertical_speed = max(screen_height * 0.24, 10.0)
    start_offset = radius + (paddle_width / 2) + 1

    return CubePongState(
        screen_width=screen_width,
        screen_height=screen_height,
        paddle_one_y=screen_height / 2,
        paddle_two_y=screen_height / 2,
        balls=(
            CubePongBall(
                route_name=ROUTE_ACROSS_SCREEN_TWO,
                x=paddle_one_x + start_offset,
                y=screen_height * 0.35,
                vx=ball_speed,
                vy=vertical_speed,
            ),
            CubePongBall(
                route_name=ROUTE_ACROSS_SCREEN_FOUR,
                x=paddle_one_x + start_offset,
                y=screen_height * 0.65,
                vx=ball_speed,
                vy=-vertical_speed,
            ),
        ),
        player_one_score=player_one_score,
        player_two_score=player_two_score,
    )


def advance_cube_pong_state(
    state: CubePongState,
    controls: CubePongControls,
    delta_s: float,
) -> CubePongState:
    delta_s = max(0.0, min(delta_s, 0.05))
    if state.losing_player is not None:
        remaining = state.reset_remaining_s - delta_s
        if remaining <= 0:
            return _new_cube_pong_round(
                state.screen_width,
                state.screen_height,
                player_one_score=state.player_one_score,
                player_two_score=state.player_two_score,
            )
        return CubePongState(
            screen_width=state.screen_width,
            screen_height=state.screen_height,
            paddle_one_y=state.paddle_one_y,
            paddle_two_y=state.paddle_two_y,
            balls=state.balls,
            player_one_score=state.player_one_score,
            player_two_score=state.player_two_score,
            losing_player=state.losing_player,
            reset_remaining_s=remaining,
        )

    paddle_speed = max(state.screen_height * 1.9, 80.0)
    paddle_one_y = _move_paddle(
        state.paddle_one_y,
        controls.player_one,
        paddle_speed,
        delta_s,
        state.screen_width,
        state.screen_height,
    )
    paddle_two_y = _move_paddle(
        state.paddle_two_y,
        controls.player_two,
        paddle_speed,
        delta_s,
        state.screen_width,
        state.screen_height,
    )

    balls: list[CubePongBall] = []
    for ball in state.balls:
        next_ball, losing_player = _advance_ball(
            ball,
            state.screen_width,
            state.screen_height,
            paddle_one_y,
            paddle_two_y,
            delta_s,
        )
        balls.append(next_ball)
        if losing_player is not None:
            player_one_score = state.player_one_score
            player_two_score = state.player_two_score
            if losing_player == PLAYER_ONE:
                player_two_score += 1
            else:
                player_one_score += 1
            updated_balls = [state.balls[0], state.balls[1]]
            for index, updated_ball in enumerate(balls):
                updated_balls[index] = updated_ball
            return CubePongState(
                screen_width=state.screen_width,
                screen_height=state.screen_height,
                paddle_one_y=paddle_one_y,
                paddle_two_y=paddle_two_y,
                balls=(updated_balls[0], updated_balls[1]),
                player_one_score=player_one_score,
                player_two_score=player_two_score,
                losing_player=losing_player,
                reset_remaining_s=ROUND_RESET_HOLD_S,
            )

    return CubePongState(
        screen_width=state.screen_width,
        screen_height=state.screen_height,
        paddle_one_y=paddle_one_y,
        paddle_two_y=paddle_two_y,
        balls=(balls[0], balls[1]),
        player_one_score=state.player_one_score,
        player_two_score=state.player_two_score,
    )


def face_position_for_ball(
    ball: CubePongBall, screen_width: int
) -> FacePosition | None:
    route = ROUTES[ball.route_name]
    court_width = screen_width * len(route.faces)
    if ball.x < 0 or ball.x > court_width:
        return None
    segment = min(int(ball.x // screen_width), len(route.faces) - 1)
    local_x = ball.x - segment * screen_width
    return FacePosition(face_index=route.faces[segment], x=local_x, y=ball.y)


def paddle_size(screen_width: int, screen_height: int) -> tuple[int, int]:
    width = max(3, round(screen_width * 0.06))
    height = max(14, round(screen_height * 0.34))
    return width, min(height, screen_height)


def ball_radius(screen_width: int) -> int:
    return max(3, round(screen_width * 0.045))


def paddle_path_x(screen_width: int) -> tuple[float, float]:
    return screen_width * 0.5, screen_width * 2.5


def base_ball_speed(screen_width: int) -> float:
    return max(screen_width * 0.95, 42.0)


def _advance_ball(
    ball: CubePongBall,
    screen_width: int,
    screen_height: int,
    paddle_one_y: float,
    paddle_two_y: float,
    delta_s: float,
) -> tuple[CubePongBall, int | None]:
    radius = ball_radius(screen_width)
    next_x = ball.x + ball.vx * delta_s
    next_y = ball.y + ball.vy * delta_s
    next_vx = ball.vx
    next_vy = ball.vy

    if next_y <= radius:
        next_y = radius
        next_vy = abs(next_vy)
    elif next_y >= screen_height - radius:
        next_y = screen_height - radius
        next_vy = -abs(next_vy)

    paddle_one_x, paddle_two_x = paddle_path_x(screen_width)
    paddle_width, paddle_height = paddle_size(screen_width, screen_height)
    half_width = paddle_width / 2
    max_speed = base_ball_speed(screen_width) * 1.45
    route = ROUTES[ball.route_name]

    if next_vx > 0:
        defending_player = route.end_player
        defending_paddle_y = _paddle_y_for_player(
            defending_player,
            paddle_one_y,
            paddle_two_y,
        )
        contact_x = paddle_two_x - half_width - radius
        missed_x = paddle_two_x + half_width + radius
        if ball.x <= contact_x <= next_x:
            hit_offset = _hit_offset(
                next_y,
                defending_paddle_y,
                paddle_height,
                radius,
            )
            if hit_offset is None:
                return (
                    CubePongBall(ball.route_name, next_x, next_y, next_vx, next_vy),
                    defending_player,
                )
            next_x = contact_x
            next_vx = -min(abs(next_vx) * 1.02, max_speed)
            next_vy = _spin_velocity(next_vy, hit_offset, screen_height)
        elif next_x > missed_x:
            return (
                CubePongBall(ball.route_name, next_x, next_y, next_vx, next_vy),
                defending_player,
            )
    else:
        defending_player = route.start_player
        defending_paddle_y = _paddle_y_for_player(
            defending_player,
            paddle_one_y,
            paddle_two_y,
        )
        contact_x = paddle_one_x + half_width + radius
        missed_x = paddle_one_x - half_width - radius
        if ball.x >= contact_x >= next_x:
            hit_offset = _hit_offset(
                next_y,
                defending_paddle_y,
                paddle_height,
                radius,
            )
            if hit_offset is None:
                return (
                    CubePongBall(ball.route_name, next_x, next_y, next_vx, next_vy),
                    defending_player,
                )
            next_x = contact_x
            next_vx = min(abs(next_vx) * 1.02, max_speed)
            next_vy = _spin_velocity(next_vy, hit_offset, screen_height)
        elif next_x < missed_x:
            return (
                CubePongBall(ball.route_name, next_x, next_y, next_vx, next_vy),
                defending_player,
            )

    return CubePongBall(ball.route_name, next_x, next_y, next_vx, next_vy), None


def _move_paddle(
    current_y: float,
    control: float,
    paddle_speed: float,
    delta_s: float,
    screen_width: int,
    screen_height: int,
) -> float:
    _, paddle_height = paddle_size(screen_width, screen_height)
    half_height = paddle_height / 2
    next_y = current_y + _clamp(control, -1.0, 1.0) * paddle_speed * delta_s
    return _clamp(next_y, half_height, screen_height - half_height)


def _paddle_y_for_player(
    player: int,
    paddle_one_y: float,
    paddle_two_y: float,
) -> float:
    return paddle_one_y if player == PLAYER_ONE else paddle_two_y


def _hit_offset(
    ball_y: float,
    paddle_y: float,
    paddle_height: int,
    radius: int,
) -> float | None:
    half_height = paddle_height / 2
    if abs(ball_y - paddle_y) > half_height + radius:
        return None
    return _clamp((ball_y - paddle_y) / max(half_height, 1), -1.0, 1.0)


def _spin_velocity(current_vy: float, hit_offset: float, screen_height: int) -> float:
    spin = hit_offset * max(screen_height * 0.48, 16.0)
    return _clamp(current_vy + spin, -screen_height * 1.1, screen_height * 1.1)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
