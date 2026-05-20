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

    def test_cradle_swing_alternates_between_outer_balls(self) -> None:
        first_half = BouncingBallRenderer._swing_angles(0.65)
        second_half = BouncingBallRenderer._swing_angles(1.95)

        assert first_half[0] < 0.0
        assert first_half[-1] == 0.0
        assert second_half[0] == 0.0
        assert second_half[-1] > 0.0

    def test_cradle_rest_centers_are_evenly_spaced(self) -> None:
        centers = BouncingBallRenderer._rest_centers(
            rect=pygame.Rect(0, 0, 256, 64),
            radius=6,
        )

        assert len(centers) == 5
        assert centers[2] == 128
        assert centers[1] - centers[0] == centers[2] - centers[1]

    def test_cradle_frame_stays_inside_display(self) -> None:
        rect = pygame.Rect(64, 0, 64, 64)
        frame = BouncingBallRenderer._cradle_frame(rect)

        assert rect.contains(frame)
        assert frame.left > rect.left
        assert frame.top > rect.top
        assert frame.bottom < rect.bottom

    def test_cradle_uses_side_views_on_a_and_c_panels(self) -> None:
        views = tuple(BouncingBallRenderer._panel_view(index) for index in range(4))

        assert views == ("left_side", "front", "right_side", "front")

    def test_left_side_view_scales_left_swinging_ball_toward_viewer(self) -> None:
        resting = BouncingBallRenderer._side_view_depth_scale(0.0, view_sign=-1.0)
        left_swinging = BouncingBallRenderer._side_view_depth_scale(
            -0.92,
            view_sign=-1.0,
        )
        right_swinging = BouncingBallRenderer._side_view_depth_scale(
            0.92,
            view_sign=-1.0,
        )

        assert left_swinging > resting
        assert left_swinging > 1.6
        assert right_swinging == resting

    def test_right_side_view_scales_right_swinging_ball_toward_viewer(self) -> None:
        resting = BouncingBallRenderer._side_view_depth_scale(0.0, view_sign=1.0)
        left_swinging = BouncingBallRenderer._side_view_depth_scale(
            -0.92,
            view_sign=1.0,
        )
        right_swinging = BouncingBallRenderer._side_view_depth_scale(
            0.92,
            view_sign=1.0,
        )

        assert right_swinging > resting
        assert right_swinging > 1.6
        assert left_swinging == resting

    def test_far_side_view_keeps_swinging_ball_pink(self) -> None:
        renderer = BouncingBallRenderer()
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)

        renderer._draw_cradle(
            screen=surface,
            rect=pygame.Rect(0, 0, 64, 64),
            elapsed_s=0.65,
            view="right_side",
        )

        upper_magenta_pixels = self._count_pixels_matching(
            surface,
            max_y=42,
            predicate=lambda color: color.r > 180 and color.b > 150 and color.g < 120,
        )
        assert upper_magenta_pixels > 0

    def test_side_view_keeps_swinging_ball_on_vertical_line(self) -> None:
        renderer = BouncingBallRenderer()
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)

        renderer._draw_cradle(
            screen=surface,
            rect=pygame.Rect(0, 0, 64, 64),
            elapsed_s=0.65,
            view="left_side",
        )

        bright_x_values = [
            x
            for x in range(surface.get_width())
            for y in range(surface.get_height())
            if surface.get_at((x, y)).r > 80
        ]
        center_x = surface.get_width() // 2
        rendered_midpoint = (min(bright_x_values) + max(bright_x_values)) / 2
        assert abs(rendered_midpoint - center_x) <= 0.5

    def test_cradle_drawing_restores_panel_clip(self) -> None:
        renderer = BouncingBallRenderer()
        surface = pygame.Surface((128, 64), pygame.SRCALPHA)
        original_clip = surface.get_clip()

        renderer._draw_clipped_cradle(
            screen=surface,
            rect=pygame.Rect(0, 0, 64, 64),
            elapsed_s=0.65,
            view="left_side",
        )

        assert surface.get_clip() == original_clip
        assert self._count_bright_pixels(surface.subsurface(pygame.Rect(64, 0, 64, 64))) == 0

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

    def test_render_draws_newtons_cradle_across_four_panel_views(self, device) -> None:
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

        bright_pixels = self._count_bright_pixels(surface)
        side_panel_pixels = self._count_bright_pixels(
            surface.subsurface(pygame.Rect(0, 0, 64, 64))
        )
        front_panel_pixels = self._count_bright_pixels(
            surface.subsurface(pygame.Rect(64, 0, 64, 64))
        )

        assert bright_pixels > 120
        assert side_panel_pixels != front_panel_pixels

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

    def _count_pixels_matching(
        self,
        surface: pygame.Surface,
        *,
        max_y: int,
        predicate,
    ) -> int:
        return sum(
            1
            for x in range(surface.get_width())
            for y in range(max_y)
            if predicate(surface.get_at((x, y)))
        )
