from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import pygame

from heart import DeviceDisplayMode
from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.rendering.surface_provider import RendererSurfaceProvider
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

logger = get_logger(__name__)
log_controller = get_logging_controller()


class RendererProcessor:
    def __init__(
        self,
        device: Device,
        peripheral_manager: PeripheralManager,
        surface_provider: RendererSurfaceProvider,
    ) -> None:
        self.device = device
        self.peripheral_manager = peripheral_manager
        self._surface_provider = surface_provider

    def _prepare_renderer_surface(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        return self._surface_provider.prepare(renderer)

    def _render_renderer_frame(
        self, renderer: "StatefulBaseRenderer[Any]", clock: pygame.time.Clock
    ) -> pygame.Surface:
        screen = self._prepare_renderer_surface(renderer)
        if not renderer.initialized:
            renderer.initialize(
                window=screen,
                clock=clock,
                peripheral_manager=self.peripheral_manager,
                orientation=self.device.orientation,
            )
        renderer._internal_process(
            window=screen,
            clock=clock,
            peripheral_manager=self.peripheral_manager,
            orientation=self.device.orientation,
        )
        return screen

    def _log_renderer_metrics(
        self,
        renderer: "StatefulBaseRenderer[Any]",
        duration_ms: float,
        queue_depth: int,
    ) -> None:
        log_message = (
            "render.loop renderer=%s duration_ms=%.2f queue_depth=%s "
            "display_mode=%s uses_opengl=%s initialized=%s"
        )
        log_args = (
            renderer.name,
            duration_ms,
            queue_depth,
            renderer.device_display_mode.name,
            renderer.device_display_mode == DeviceDisplayMode.OPENGL,
            renderer.is_initialized(),
        )
        log_extra = {
            "renderer": renderer.name,
            "duration_ms": duration_ms,
            "queue_depth": queue_depth,
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

    def process_renderer(
        self,
        renderer: "StatefulBaseRenderer[Any]",
        clock: pygame.time.Clock,
        queue_depth: int,
    ) -> pygame.Surface | None:
        try:
            start_ns = time.perf_counter_ns()
            screen = self._render_renderer_frame(renderer, clock)
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            self._log_renderer_metrics(renderer, duration_ms, queue_depth)
            return screen
        except Exception:
            logger.exception("Error processing renderer")
            return None
