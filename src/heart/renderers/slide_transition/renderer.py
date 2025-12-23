import logging
import time

import pygame

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
        super().__init__()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> SlideTransitionState:
        initial_state = self.provider.initial_state(
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        self.set_state(initial_state)
        self._subscription = self.provider.observable(
            peripheral_manager,
            initial_state=initial_state,
        ).subscribe(on_next=self.set_state)
        return initial_state

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
