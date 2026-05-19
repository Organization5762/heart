from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Cube
from heart.peripheral.core.input.frame import FrameTick
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.sensor import Acceleration
from heart.renderers.bouncing_ball import (BallPosition, BallVelocity,
                                           BouncingBallRenderer,
                                           BouncingBallState,
                                           BouncingBallStateProvider)
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

    def test_far_projection_converges_toward_adjacent_wall_precipice(self) -> None:
        renderer = BouncingBallRenderer()
        rect = pygame.Rect(0, 0, 100, 80)

        projected_x, projected_y, _radius, far_depth = renderer._project_ball(
            rect=rect,
            position=BallPosition(x=0.0, y=0.0, z=1.0),
            side_index=0,
        )

        assert far_depth == 0.0
        assert projected_x > rect.centerx
        assert abs(projected_y - rect.centery) <= 1

    def test_precipice_point_uses_lateral_side_of_face(self) -> None:
        rect = pygame.Rect(10, 20, 80, 60)

        assert BouncingBallRenderer._precipice_point(rect=rect, lateral=0.5) == (
            rect.right - 1,
            rect.centery,
        )
        assert BouncingBallRenderer._precipice_point(rect=rect, lateral=-0.5) == (
            rect.left,
            rect.centery,
        )

    def test_face_lateral_rotates_with_cube_side(self) -> None:
        position = BallPosition(x=0.8, y=0.0, z=-0.4)

        assert BouncingBallRenderer._face_lateral(position=position, side_index=0) > 0.0
        assert BouncingBallRenderer._face_lateral(position=position, side_index=1) < 0.0

    def test_adjacent_panel_polygon_projects_from_selected_side_edge(self) -> None:
        rect = pygame.Rect(0, 0, 100, 80)

        right_panel = BouncingBallRenderer._adjacent_panel_polygon(
            rect=rect,
            lateral=1.0,
        )
        left_panel = BouncingBallRenderer._adjacent_panel_polygon(
            rect=rect,
            lateral=-1.0,
        )

        assert right_panel[0][0] == rect.right - 1
        assert right_panel[2][0] < right_panel[0][0]
        assert left_panel[0][0] == rect.left
        assert left_panel[2][0] > left_panel[0][0]

    def test_runway_segments_stack_toward_precipice_by_hypotenuse(self) -> None:
        rect = pygame.Rect(0, 0, 96, 64)

        segments = BouncingBallRenderer._runway_segments(rect=rect, lateral=1.0)

        assert len(segments) >= 6
        first_floor_start, first_floor_end = segments[0]
        last_floor_start, last_floor_end = segments[-2]
        assert first_floor_start[1] > last_floor_start[1]
        assert first_floor_end[0] <= rect.right - 1
        assert last_floor_end[0] <= rect.right - 1

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

    def test_provider_uses_accelerometer_force_to_change_velocity(self) -> None:
        provider = BouncingBallStateProvider()
        initial = BouncingBallState(
            position=BallPosition(x=0.0, y=0.0, z=0.0),
            velocity=BallVelocity(x=0.0, y=0.0, z=0.0),
            last_time_s=0.0,
        )

        resting = provider._advance_state(
            state=initial,
            frame_tick=self._frame_tick(index=1, delta_s=0.05),
            acceleration=Acceleration(x=0.0, y=0.0, z=9.81),
        )
        state = provider._advance_state(
            state=resting,
            frame_tick=self._frame_tick(index=2, delta_s=0.05),
            acceleration=Acceleration(x=4.0, y=2.0, z=12.0),
        )

        assert state.velocity.x > 0.0
        assert state.velocity.y > 0.0
        assert state.velocity.z > 0.0

    def test_provider_deadbands_resting_accelerometer_noise(self) -> None:
        provider = BouncingBallStateProvider()
        initial = BouncingBallState(
            position=BallPosition(x=0.0, y=0.0, z=0.0),
            velocity=BallVelocity(x=0.0, y=0.0, z=0.0),
            last_time_s=0.0,
        )

        resting = provider._advance_state(
            state=initial,
            frame_tick=self._frame_tick(index=1, delta_s=0.05),
            acceleration=Acceleration(x=0.0, y=0.0, z=9.81),
        )
        state = provider._advance_state(
            state=resting,
            frame_tick=self._frame_tick(index=2, delta_s=0.05),
            acceleration=Acceleration(x=0.08, y=-0.11, z=9.93),
        )

        assert state.force == BallVelocity(x=0.0, y=0.0, z=0.0)
        assert state.velocity == BallVelocity(x=0.0, y=0.0, z=0.0)

    def test_provider_force_decays_after_motion_stops(self) -> None:
        provider = BouncingBallStateProvider()
        initial = BouncingBallState(
            position=BallPosition(x=0.0, y=0.0, z=0.0),
            velocity=BallVelocity(x=0.0, y=0.0, z=0.0),
            last_time_s=0.0,
        )

        resting = provider._advance_state(
            state=initial,
            frame_tick=self._frame_tick(index=1, delta_s=0.05),
            acceleration=Acceleration(x=0.0, y=0.0, z=9.81),
        )
        pushed = provider._advance_state(
            state=resting,
            frame_tick=self._frame_tick(index=2, delta_s=0.05),
            acceleration=Acceleration(x=6.0, y=0.0, z=9.81),
        )
        decayed = provider._advance_state(
            state=pushed,
            frame_tick=self._frame_tick(index=3, delta_s=0.2),
            acceleration=None,
        )

        assert 0.0 < abs(decayed.force.x) < abs(pushed.force.x)

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

    def _frame_tick(self, *, index: int, delta_s: float) -> FrameTick:
        return FrameTick(
            frame_index=index,
            delta_ms=delta_s * 1000.0,
            delta_s=delta_s,
            monotonic_s=index * delta_s,
        )

    def _count_bright_pixels(self, surface: pygame.Surface) -> int:
        return sum(
            1
            for x in range(surface.get_width())
            for y in range(surface.get_height())
            if surface.get_at((x, y)).r > 80
        )
