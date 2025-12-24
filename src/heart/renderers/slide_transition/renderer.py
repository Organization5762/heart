import logging
import time

import pygame
import reactivex

from heart import DeviceDisplayMode
from heart.device import Orientation, Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.slide_transition.provider import SlideTransitionProvider
from heart.renderers.slide_transition.state import SlideTransitionState
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

logger = get_logger(__name__)
log_controller = get_logging_controller()


class SlideTransitionRenderer(StatefulBaseRenderer[SlideTransitionState]):
    """Slides renderer_B into view while renderer_A moves out."""

    def __init__(self, provider: SlideTransitionProvider) -> None:
        self.provider = provider
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self._initial_state: SlideTransitionState | None = None
        super().__init__(builder=self.provider)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._initialize_children(window, clock, peripheral_manager, orientation)
        self._initial_state = self.provider.initial_state(
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        super().initialize(window, clock, peripheral_manager, orientation)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[SlideTransitionState]:
        if self._initial_state is None:
            raise ValueError("SlideTransitionRenderer requires an initial state")
        return self.provider.observable(
            peripheral_manager,
            initial_state=self._initial_state,
        )

    def _initialize_children(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        for renderer in (self.provider.renderer_a, self.provider.renderer_b):
            if not renderer.initialized:
                renderer.initialize(
                    window=window,
                    clock=clock,
                    peripheral_manager=peripheral_manager,
                    orientation=orientation,
                )
                renderer.initialized = True

    def is_done(self) -> bool:
        return not self.state.sliding

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state

        size = window.get_size()
        surf_a = pygame.Surface(size, pygame.SRCALPHA)
        surf_b = pygame.Surface(size, pygame.SRCALPHA)

        start_ns = time.perf_counter_ns()
        self.provider.renderer_a._internal_process(
            surf_a, clock, state.peripheral_manager, Rectangle.with_layout(1, 1)
        )
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        log_controller.log(
            key="render.loop",
            logger=logger,
            level=logging.INFO,
            msg="slide.A renderer=%s duration_ms=%.2f",
            args=(self.provider.renderer_a.name, duration_ms),
        )

        start_ns = time.perf_counter_ns()
        self.provider.renderer_b._internal_process(
            surf_b, clock, state.peripheral_manager, Rectangle.with_layout(1, 1)
        )
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        log_controller.log(
            key="render.loop",
            logger=logger,
            level=logging.INFO,
            msg="slide.B renderer=%s duration_ms=%.2f",
            args=(self.provider.renderer_b.name, duration_ms),
        )

        offset_a = (state.x_offset, 0)
        offset_b = (state.x_offset + self.provider.direction * state.screen_w, 0)

        window.blit(surf_a, offset_a)
        window.blit(surf_b, offset_b)
