from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import pygame

from heart import DeviceDisplayMode
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.surface.provider import RendererSurfaceProvider
from heart.runtime.rendering.timing import RendererTimingTracker
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

if TYPE_CHECKING:
    from heart.device import Device
    from heart.peripheral.core.manager import PeripheralManager
    from heart.renderers import StatefulBaseRenderer

logger = get_logger(__name__)
log_controller = get_logging_controller()


class RendererProcessor:
    def __init__(self, display_context: DisplayContext, peripheral_manager: PeripheralManager) -> None:
        self.peripheral_manager = peripheral_manager
        self.clock: pygame.time.Clock | None = None
        self.display_context = display_context
        self._surface_provider = RendererSurfaceProvider(display_context)
        self._timing_tracker = RendererTimingTracker(
            strategy=Configuration.render_timing_strategy(),
            ema_alpha=Configuration.render_timing_ema_alpha(),
        )
        self._render_queue_depth = 0

    @property
    def timing_tracker(self) -> RendererTimingTracker:
        return self._timing_tracker

    def set_clock(self, clock: pygame.time.Clock | None) -> None:
        self.clock = clock

    def set_queue_depth(self, depth: int) -> None:
        self._render_queue_depth = depth

    def process_renderer(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface | None:
        try:
            start_ns = time.perf_counter_ns()
            screen = self._render_frame_using_renderer(renderer)
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            self._timing_tracker.record(renderer.name, duration_ms)
            self._log_renderer_metrics(renderer, duration_ms)
            return screen
        except Exception:
            logger.exception("Error processing renderer")
            return None

    def _render_frame_using_renderer(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        scratch_context = self.display_context.get_scratch_screen(
            orientation=self.display_context.device.orientation,
            display_mode=renderer.device_display_mode,
        )

        if not renderer.initialized:
            renderer.initialize(
                window=scratch_context,
                peripheral_manager=self.peripheral_manager,
                orientation=self.display_context.device.orientation,
            )
        renderer._internal_process(
            window=scratch_context,
            peripheral_manager=self.peripheral_manager,
            orientation=self.display_context.device.orientation,
        )
        screen = self._surface_provider.postprocess_input_screen(
            screen=scratch_context.screen,
            orientation=self.display_context.device.orientation,
            display_mode=renderer.device_display_mode
        )
        return screen

    def _log_renderer_metrics(
        self, renderer: "StatefulBaseRenderer[Any]", duration_ms: float
    ) -> None:
        log_message = (
            "render.loop renderer=%s duration_ms=%.2f queue_depth=%s "
            "display_mode=%s uses_opengl=%s initialized=%s"
        )
        log_args = (
            renderer.name,
            duration_ms,
            self._render_queue_depth,
            renderer.device_display_mode.name,
            renderer.device_display_mode == DeviceDisplayMode.OPENGL,
            renderer.is_initialized(),
        )
        log_extra = {
            "renderer": renderer.name,
            "duration_ms": duration_ms,
            "queue_depth": self._render_queue_depth,
            "display_mode": renderer.device_display_mode.name,
            "uses_opengl": renderer.device_display_mode == DeviceDisplayMode.OPENGL,
            "initialized": renderer.is_initialized(),
        }

        log_controller.log(
            key="render.loop",
            logger=logger,
            level=logging.INFO,
            msg=log_message,
            args=log_args,
            extra=log_extra,
            fallback_level=logging.DEBUG,
        )
