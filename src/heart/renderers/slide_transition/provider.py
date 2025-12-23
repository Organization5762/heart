from __future__ import annotations

from dataclasses import replace

import pygame

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import BaseRenderer
from heart.renderers.slide_transition.state import SlideTransitionState


class SlideTransitionProvider:
    def __init__(
        self,
        renderer_a: BaseRenderer,
        renderer_b: BaseRenderer,
        *,
        direction: int = 1,
        slide_speed: int = 10,
    ) -> None:
        self.renderer_a = renderer_a
        self.renderer_b = renderer_b
        self.direction = 1 if direction >= 0 else -1
        self.slide_speed = slide_speed

    def _initialize_children(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.renderer_a.initialized:
            self.renderer_a.initialize(
                window=window,
                clock=clock,
                peripheral_manager=peripheral_manager,
                orientation=orientation,
            )
            self.renderer_a.initialized = True

        if not self.renderer_b.initialized:
            self.renderer_b.initialize(
                window=window,
                clock=clock,
                peripheral_manager=peripheral_manager,
                orientation=orientation,
            )
            self.renderer_b.initialized = True

    def initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> SlideTransitionState:
        self._initialize_children(window, clock, peripheral_manager, orientation)
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
