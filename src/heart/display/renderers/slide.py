import logging
import time
from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation, Rectangle
from heart.display.renderers import AtomicBaseRenderer, BaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

logger = get_logger(__name__)
log_controller = get_logging_controller()

@dataclass
class SlideTransitionState:
    peripheral_manager: PeripheralManager
    x_offset: int = 0
    target_offset: int | None = None
    sliding: bool = True
    screen_w: int = 0


class SlideTransitionRenderer(AtomicBaseRenderer[SlideTransitionState]):
    """Slides renderer_B into view while renderer_A moves out.

    direction  =  1  → B comes from the right  (A → left) direction  = -1  → B comes
    from the left   (A → right)

    """

    def __init__(
        self,
        renderer_A: BaseRenderer,
        renderer_B: BaseRenderer,
        *,
        direction: int = 1,
        slide_speed: int = 10,
    ) -> None:
        self.renderer_A = renderer_A
        self.renderer_B = renderer_B
        self.direction = 1 if direction >= 0 else -1
        self.slide_speed = slide_speed  # Use the parameter value instead of hardcoding

        self.device_display_mode = DeviceDisplayMode.MIRRORED
        AtomicBaseRenderer.__init__(self)

        self.peripheral_manager = None

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
        self.peripheral_manager = peripheral_manager
        if not self.renderer_A.initialized:
            self.renderer_A.initialize(
                window=window,
                clock=clock,
                peripheral_manager=peripheral_manager,
                orientation=orientation
            )
            # TODO: Why do i need to set this and it isn't set by the underlying
            self.renderer_A.initialized = True

        if not self.renderer_B.initialized:
            self.renderer_B.initialize(
                window=window,
                clock=clock,
                peripheral_manager=peripheral_manager,
                orientation=orientation
            )
            # TODO: Why do i need to set this and it isn't set by the underlying
            self.renderer_B.initialized = True
        # meh hack so that we can persist this to real_process for now to support non-migrated renderers
        return SlideTransitionState(
            peripheral_manager=self.peripheral_manager
        )

    def is_done(self) -> bool:
        return not self.state.sliding

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        """
        1. Lazily work out screen width / target.
        2. Advance the slide (updates the atomic state offset).
        3. Ask each child renderer to draw onto its own temp surface.
        4. Blit those temps to `window` at their current offsets.
        """
        # ----------------------------------------------------------------- #
        # lazy-init measurements
        # ----------------------------------------------------------------- #
        state = self.state

        screen_w = window.get_width()
        if state.target_offset is None or state.screen_w != screen_w:
            target_offset = -self.direction * screen_w
            self.update_state(
                target_offset=target_offset,
                screen_w=screen_w,
            )
            state = self.state

        # ----------------------------------------------------------------- #
        # 1. advance the slide
        # ----------------------------------------------------------------- #
        if state.sliding and state.target_offset is not None:
            dist = state.target_offset - state.x_offset
            step_size = (
                dist
                if abs(dist) <= self.slide_speed  # snap on final frame
                else self.slide_speed * (1 if dist > 0 else -1)
            )
            new_offset = state.x_offset + step_size
            still_sliding = True

            # Check if we've reached or passed the target in either direction
            if (self.direction > 0 and new_offset <= state.target_offset) or (
                self.direction < 0 and new_offset >= state.target_offset
            ):
                new_offset = state.target_offset
                still_sliding = False

            self.update_state(x_offset=new_offset, sliding=still_sliding)
            state = self.state

        # ----------------------------------------------------------------- #
        # 2. render both children to off-screen surfaces
        # ----------------------------------------------------------------- #
        size = window.get_size()
        surf_A = pygame.Surface(size, pygame.SRCALPHA)
        surf_B = pygame.Surface(size, pygame.SRCALPHA)

        # This will break any composed renderer
        start_ns = time.perf_counter_ns()
        self.renderer_A._internal_process(
            surf_A, clock, self.state.peripheral_manager, Rectangle.with_layout(1, 1)
        )
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        log_message = (
            "slide.A renderer=%s duration_ms=%.2f"
        )
        log_args = (
            self.renderer_A.name,
            duration_ms,
        )
        log_controller.log(
            key="render.loop",
            logger=logger,
            level=logging.INFO,
            msg=log_message,
            args=log_args
        )
        start_ns = time.perf_counter_ns()
        self.renderer_B._internal_process(
            surf_B, clock, self.state.peripheral_manager, Rectangle.with_layout(1, 1)
        )
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        log_message = (
            "slide.B renderer=%s duration_ms=%.2f"
        )
        log_args = (
            self.renderer_B.name,
            duration_ms,
        )
        log_controller.log(
            key="render.loop",
            logger=logger,
            level=logging.INFO,
            msg=log_message,
            args=log_args
        )

        # ----------------------------------------------------------------- #
        # 3. blit at their current offsets
        #    A : starts 0 → slides to ±screen_w
        #    B : starts ±screen_w → slides to 0
        # ----------------------------------------------------------------- #
        offset_A = (state.x_offset, 0)
        offset_B = (state.x_offset + self.direction * state.screen_w, 0)

        # Draw the renderers at their current positions
        window.blit(surf_A, offset_A)
        window.blit(surf_B, offset_B)
