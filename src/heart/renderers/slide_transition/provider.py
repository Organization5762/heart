from __future__ import annotations

from dataclasses import replace

import pygame
import reactivex
from reactivex import operators as ops

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers import StatefulBaseRenderer
from heart.renderers.slide_transition.state import SlideTransitionState
from heart.utilities.reactivex_threads import pipe_in_background


class SlideTransitionProvider(ObservableProvider[SlideTransitionState]):
    def __init__(
        self,
        renderer_a: StatefulBaseRenderer,
        renderer_b: StatefulBaseRenderer,
        *,
        direction: int = 1,
        slide_speed: int = 10,
    ) -> None:
        self.renderer_a = renderer_a
        self.renderer_b = renderer_b
        self.direction = 1 if direction >= 0 else -1
        self.slide_speed = slide_speed

    def initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> SlideTransitionState:
        screen_w = window.get_width()
        return self._with_screen_width(
            SlideTransitionState(peripheral_manager=peripheral_manager),
            screen_w=screen_w,
            direction=self.direction,
        )

    def update_state(
        self, *, state: SlideTransitionState, screen_width: int
    ) -> SlideTransitionState:
        refreshed_state = self._with_screen_width(
            state, screen_w=screen_width, direction=self.direction
        )
        return self._advance(
            state=refreshed_state,
            direction=self.direction,
            slide_speed=self.slide_speed,
        )

    def observable(
        self,
        peripheral_manager: PeripheralManager,
        *,
        initial_state: SlideTransitionState,
    ) -> reactivex.Observable[SlideTransitionState]:
        window_widths = pipe_in_background(
            peripheral_manager.window,
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: window.get_width()),
            ops.distinct_until_changed(),
            ops.start_with(initial_state.screen_w),
        )

        tick_updates = pipe_in_background(
            peripheral_manager.game_tick,
            ops.filter(lambda tick: tick is not None),
            ops.with_latest_from(window_widths),
            ops.map(
                lambda latest: lambda state: self.update_state(
                    state=state,
                    screen_width=latest[1],
                )
            ),
        )

        return pipe_in_background(
            tick_updates,
            ops.scan(lambda state, update: update(state), seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

    @staticmethod
    def _with_screen_width(
        state: SlideTransitionState, *, screen_w: int, direction: int
    ) -> SlideTransitionState:
        if state.target_offset is None or state.screen_w != screen_w:
            return replace(state, screen_w=screen_w, target_offset=-direction * screen_w)
        return state

    @staticmethod
    def _advance(
        *,
        state: SlideTransitionState,
        direction: int,
        slide_speed: int,
    ) -> SlideTransitionState:
        if not state.sliding or state.target_offset is None:
            return state

        dist = state.target_offset - state.x_offset
        step_size = (
            dist
            if abs(dist) <= slide_speed
            else slide_speed * (1 if dist > 0 else -1)
        )
        new_offset = state.x_offset + step_size
        still_sliding = True

        if (direction > 0 and new_offset <= state.target_offset) or (
            direction < 0 and new_offset >= state.target_offset
        ):
            new_offset = state.target_offset
            still_sliding = False

        return replace(state, x_offset=new_offset, sliding=still_sliding)
