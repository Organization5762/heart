from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pygame
from lagom import Container

from heart.device import Device
from heart.navigation import AppController, ComposedRenderer, MultiScene
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import container
from heart.runtime.display_context import DisplayContext
from heart.runtime.event_pump import EventPump
from heart.runtime.frame_presenter import FramePresenter
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.runtime.render_pipeline import RendererVariant, RenderPipeline
from heart.utilities.logging import get_logger

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

logger = get_logger(__name__)

ACTIVE_GAME_LOOP: "GameLoop" | None = None


class GameLoop:
    def __init__(
        self,
        device: Device,
        resolver: Container,
        max_fps: int = 500,
        render_variant: RendererVariant = RendererVariant.ITERATIVE,
    ) -> None:
        self.context_container = resolver
        self.initialized = False
        self.device = device
        self.peripheral_manager = container.resolve(PeripheralManager)
        self.peripheral_runtime = PeripheralRuntime(self.peripheral_manager)

        self.max_fps = max_fps
        self.app_controller = AppController()
        self.display = DisplayContext(device=device)
        self.render_pipeline = RenderPipeline(
            device=device,
            peripheral_manager=self.peripheral_manager,
            render_variant=render_variant,
        )
        self.frame_presenter = FramePresenter(
            device=device,
            display=self.display,
            render_pipeline=self.render_pipeline,
        )
        self.event_pump = EventPump()

        self._active_mode_index = 0

        # Lampe controller
        self.feedback_buffer: np.ndarray | None = None
        self.edge_thresh = 1

        self.display.configure_window()

    def add_mode(
        self,
        title: str
        | list["StatefulBaseRenderer[Any]"]
        | "StatefulBaseRenderer[Any]"
        | None = None,
    ) -> ComposedRenderer:
        return self.app_controller.add_mode(title=title)

    def add_scene(self) -> MultiScene:
        return self.app_controller.add_scene()

    @classmethod
    def get_game_loop(cls) -> "GameLoop" | None:
        return ACTIVE_GAME_LOOP

    @classmethod
    def set_game_loop(cls, loop: "GameLoop") -> None:
        global ACTIVE_GAME_LOOP
        ACTIVE_GAME_LOOP = loop

    def start(self) -> None:
        logger.info("Starting GameLoop")
        if not self.initialized:
            logger.info("GameLoop not yet initialized, initializing...")
            self._ensure_initialized()
            logger.info("Finished initializing GameLoop.")

        if self.app_controller.is_empty():
            raise Exception("Unable to start as no GameModes were added.")

        # Initialize all renderers

        self.running = True
        logger.info("Entering main loop.")

        self._initialize_app_controller()
        self._ensure_display_initialized()
        self.peripheral_runtime.configure_streaming()

        try:
            self._run_main_loop()
        finally:
            self.render_pipeline.shutdown()
            pygame.quit()

    def set_screen(self, screen: pygame.Surface) -> None:
        self.display.set_screen(screen)
        self.peripheral_manager.window.on_next(self.display.screen)

    def set_clock(self, clock: pygame.time.Clock) -> None:
        self.display.set_clock(clock)
        self.render_pipeline.set_clock(clock)
        self.peripheral_manager.clock.on_next(self.display.clock)

    @property
    def screen(self) -> pygame.Surface | None:
        return self.display.screen

    @property
    def clock(self) -> pygame.time.Clock | None:
        return self.display.clock

    def _select_renderers(self) -> list["StatefulBaseRenderer[Any]"]:
        base_renderers = self.app_controller.get_renderers()
        renderers = list(base_renderers) if base_renderers else []
        return renderers

    def _one_loop(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> None:
        if self.display.screen is None:
            raise RuntimeError("GameLoop screen is not initialized")
        render_surface = self.render_pipeline.render(
            renderers, override_renderer_variant
        )
        if render_surface is not None:
            self.display.screen.blit(render_surface, (0, 0))
        self.frame_presenter.present(renderers, render_surface)

    def _preprocess_setup(self) -> None:
        self._dim_display()

    def _set_singleton(self) -> None:
        active_loop = self.get_game_loop()
        if active_loop is None:
            GameLoop.set_game_loop(self)
        elif active_loop is not self:
            logger.debug(
                "GameLoop initialized alongside existing instance; keeping original active"
            )

    def _initialize_screen(self) -> None:
        self.display.initialize()
        if self.display.screen is None or self.display.clock is None:
            raise RuntimeError("GameLoop failed to initialize display surfaces")
        self.set_screen(self.display.screen)
        self.set_clock(self.display.clock)

    def _initialize(self) -> None:
        self._set_singleton()
        self._initialize_screen()
        self.peripheral_runtime.detect_and_start()
        self.initialized = True

    def _dim_display(self) -> None:
        # Default to fully black, so the LEDs will be at lower power
        if self.display.screen is not None:
            self.display.screen.fill("black")

    def _ensure_initialized(self) -> None:
        if self.initialized:
            return
        self._initialize()

    def _initialize_app_controller(self) -> None:
        self.display.ensure_initialized()
        self.app_controller.initialize(
            window=self.display.screen,
            clock=self.display.clock,
            peripheral_manager=self.peripheral_manager,
            orientation=self.device.orientation,
        )

    def _ensure_display_initialized(self) -> None:
        self.display.ensure_initialized()

    def _run_main_loop(self) -> None:
        if self.display.clock is None:
            raise RuntimeError("GameLoop failed to initialize display clock")
        clock = self.display.clock
        while self.running:
            self.peripheral_runtime.tick()
            self.running = self.event_pump.pump(self.running)
            self._preprocess_setup()
            renderers = self._select_renderers()
            self._one_loop(renderers)
            clock.tick(self.max_fps)
