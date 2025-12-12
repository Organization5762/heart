from __future__ import annotations

import pygame

from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.display.renderers.slide_transition.state import SlideTransitionState
from heart.peripheral.core.manager import PeripheralManager


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
        return SlideTransitionState(
            peripheral_manager=peripheral_manager
        ).with_screen_width(screen_w, self.direction)

    def update_state(
        self, *, state: SlideTransitionState, screen_width: int
    ) -> SlideTransitionState:
        refreshed_state = state.with_screen_width(screen_width, self.direction)
        return refreshed_state.advance(
            direction=self.direction, slide_speed=self.slide_speed
        )
