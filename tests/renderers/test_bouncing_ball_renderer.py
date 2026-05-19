from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Cube
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.bouncing_ball import (BallPosition, BallVelocity,
                                           BouncingBallRenderer,
                                           BouncingBallState)
from heart.renderers.bouncing_ball.physics import advance_bouncing_ball_state
from heart.runtime.display_context import DisplayContext


class TestBouncingBallRenderer:
    def test_constructor_uses_full_display_mode(self) -> None:
        renderer = BouncingBallRenderer()

        assert renderer.device_display_mode == DeviceDisplayMode.FULL

    def test_projection_grows_as_ball_moves_toward_viewing_screen(self) -> None:
        renderer = BouncingBallRenderer()
        rect = pygame.Rect(0, 0, 64, 64)

        _, _, far_radius, far_depth = renderer._project_ball(
            rect=rect,
            position=BallPosition(x=0.0, y=0.0, z=1.0),
            side_index=0,
        )
        _, _, near_radius, near_depth = renderer._project_ball(
            rect=rect,
            position=BallPosition(x=0.0, y=0.0, z=-1.0),
            side_index=0,
        )

        assert near_depth > far_depth
        assert near_radius > far_radius

    def test_state_bounces_off_side_and_top_walls(self) -> None:
        renderer = BouncingBallRenderer()
        renderer.set_state(
            BouncingBallState(
                position=BallPosition(x=0.98, y=0.76, z=0.0),
                velocity=BallVelocity(x=1.0, y=1.0, z=0.0),
                last_time_s=0.0,
            )
        )

        state = advance_bouncing_ball_state(renderer.state, dt=0.1, now_s=0.1)

        assert state.position.x < 1.0
        assert state.velocity.x < 0.0
        assert state.position.y < 0.78
        assert state.velocity.y < 0.0

    def test_fast_wall_impact_spawns_smaller_child_balls(self) -> None:
        initial = BouncingBallState(
            position=BallPosition(x=0.99, y=0.0, z=0.0),
            velocity=BallVelocity(x=1.3, y=0.1, z=0.0),
            last_time_s=0.0,
        )

        state = advance_bouncing_ball_state(initial, dt=0.05, now_s=0.05)

        assert len(state.child_balls) == 3
        assert all(child.radius_scale < 0.5 for child in state.child_balls)

    def test_slow_wall_impact_does_not_spawn_child_balls(self) -> None:
        initial = BouncingBallState(
            position=BallPosition(x=0.99, y=0.0, z=0.0),
            velocity=BallVelocity(x=0.4, y=0.1, z=0.0),
            last_time_s=0.0,
        )

        state = advance_bouncing_ball_state(initial, dt=0.05, now_s=0.05)

        assert state.child_balls == ()

    def test_child_balls_decay_after_lifetime(self) -> None:
        spawned = advance_bouncing_ball_state(
            BouncingBallState(
                position=BallPosition(x=0.99, y=0.0, z=0.0),
                velocity=BallVelocity(x=1.3, y=0.1, z=0.0),
                last_time_s=0.0,
            ),
            dt=0.05,
            now_s=0.05,
        )

        decayed = advance_bouncing_ball_state(spawned, dt=1.2, now_s=1.25)

        assert decayed.child_balls == ()

    def test_render_draws_distinct_ball_sizes_across_four_screens(self, device) -> None:
        renderer = BouncingBallRenderer()
        renderer.set_state(
            BouncingBallState(
                position=BallPosition(x=0.0, y=0.0, z=-0.92),
                velocity=BallVelocity(x=0.0, y=0.0, z=0.0),
                last_time_s=0.0,
            )
        )
        renderer.initialized = True
        surface = pygame.Surface((256, 64), pygame.SRCALPHA)
        window = DisplayContext(
            device=device,
            screen=surface,
            clock=None,
            can_configure_display=False,
        )

        renderer._internal_process(window, PeripheralManager(), Cube.sides())

        first_bright_pixels = self._count_bright_pixels(
            surface.subsurface(pygame.Rect(0, 0, 64, 64))
        )
        third_bright_pixels = self._count_bright_pixels(
            surface.subsurface(pygame.Rect(128, 0, 64, 64))
        )

        assert first_bright_pixels > third_bright_pixels

    def test_projection_keeps_ball_inside_panel_bounds(self) -> None:
        renderer = BouncingBallRenderer()
        rect = pygame.Rect(0, 0, 64, 64)

        projected_x, projected_y, radius, _ = renderer._project_ball(
            rect=rect,
            position=BallPosition(x=1.0, y=0.78, z=1.0),
            side_index=1,
        )

        assert rect.left <= projected_x - radius
        assert projected_x + radius < rect.right
        assert rect.top <= projected_y - radius
        assert projected_y + radius < rect.bottom

    def _count_bright_pixels(self, surface: pygame.Surface) -> int:
        return sum(
            1
            for x in range(surface.get_width())
            for y in range(surface.get_height())
            if surface.get_at((x, y)).r > 80
        )
