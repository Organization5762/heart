import logging
import time

import reactivex

from heart import DeviceDisplayMode
from heart.device import Orientation, Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.slide_transition.provider import SlideTransitionProvider
from heart.renderers.slide_transition.state import SlideTransitionState
from heart.runtime.display_context import DisplayContext
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

logger = get_logger(__name__)
log_controller = get_logging_controller()


class SlideTransitionRenderer(StatefulBaseRenderer[SlideTransitionState]):
    """Slides renderer_B into view while renderer_A moves out."""

    def __init__(self, provider: SlideTransitionProvider,) -> None:
        self.provider = provider
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self._initial_state: SlideTransitionState | None = None
        logger.info(f"Created SlideTransitionRenderer from {provider.renderer_a.name} and {provider.renderer_b.name}")
        super().__init__(builder=self.provider)

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._initialize_children(window, peripheral_manager, orientation)
        self._initial_state = SlideTransitionState(
            peripheral_manager=peripheral_manager,
        )
        super().initialize(window, peripheral_manager, orientation)

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
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        for renderer in (self.provider.renderer_a, self.provider.renderer_b):
            if not renderer.initialized:
                renderer.initialize(
                    window=window,
                    peripheral_manager=peripheral_manager,
                    orientation=orientation,
                )
                renderer.initialized = True

    def is_done(self) -> bool:
        return not self.state.sliding

    def _render_and_log(
        self,
        renderer,
        scratch_window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
        slide_label: str,
    ) -> None:
        start_ns = time.perf_counter_ns()
        renderer._internal_process(
            scratch_window, peripheral_manager, orientation
        )
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        log_controller.log(
            key=f"render.loop.{slide_label}",
            logger=logger,
            level=logging.INFO,
            msg="renderer=%s duration_ms=%.2f",
            args=(renderer.name, duration_ms),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        state = self.state
        new_orientation = Rectangle.with_layout(1, 1)


        window_a = window.get_scratch_screen(
            orientation=new_orientation,
            display_mode=self.provider.renderer_a.device_display_mode,
        )
        window_b = window.get_scratch_screen(
            orientation=new_orientation,
            display_mode=self.provider.renderer_b.device_display_mode,
        )

        self._render_and_log(
            self.provider.renderer_a,
            window_a,
            state.peripheral_manager,
            new_orientation,
            "slide.A",
        )

        self._render_and_log(
            self.provider.renderer_b,
            window_b,
            state.peripheral_manager,
            new_orientation,
            "slide.B",
        )

        image_width = window_a.get_width()
        offset_a = (-self.provider.direction * state.fraction_offset * image_width, 0)
        offset_b = (offset_a[0] + self.provider.direction * image_width, 0)

        window.screen.blit(window_a.screen, offset_a)
        window.screen.blit(window_b.screen, offset_b)
