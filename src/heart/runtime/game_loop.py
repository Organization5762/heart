from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

import numpy as np
import pygame

from heart.device import Device
from heart.navigation import ComposedRenderer, MultiScene
from heart.runtime.container import (RuntimeContainer, build_runtime_container,
                                     configure_runtime_container)
from heart.runtime.game_loop_components import GameLoopComponents
from heart.runtime.render_pipeline import RendererVariant
from heart.utilities.logging import get_logger

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

logger = get_logger(__name__)

ACTIVE_GAME_LOOP: "GameLoop" | None = None
DependencyT = TypeVar("DependencyT")
DEFAULT_MAX_FPS = 500
DEFAULT_RENDER_VARIANT = RendererVariant.ITERATIVE
EDGE_THRESHOLD = 1


class GameLoop:
    def __init__(
        self,
        device: Device,
        resolver: RuntimeContainer | None = None,
        max_fps: int = DEFAULT_MAX_FPS,
        render_variant: RendererVariant = DEFAULT_RENDER_VARIANT,
    ) -> None:
        self.context_container = self._prepare_container(
            device=device,
            resolver=resolver,
            render_variant=render_variant,
        )
        self.initialized = False
        self.device = self.context_container.resolve(Device)

        self.max_fps = max_fps
        components = self._load_components()
        self.app_controller = components.app_controller
        self.display = components.display
        self.render_pipeline = components.render_pipeline
        self.frame_presenter = components.frame_presenter
        self.event_handler = components.event_handler
        self.peripheral_manager = components.peripheral_manager
        self.peripheral_runtime = components.peripheral_runtime

        # Lampe controller
        self.feedback_buffer: np.ndarray | None = None
        self.edge_thresh = EDGE_THRESHOLD

        self.display.configure_window()

    def resolve(self, dependency: type[DependencyT]) -> DependencyT:
        return self.context_container.resolve(dependency)

    def compose(
        self,
        renderers: list["StatefulBaseRenderer[Any]" | type["StatefulBaseRenderer[Any]"]],
    ) -> ComposedRenderer:
        return ComposedRenderer(renderers, renderer_resolver=self.context_container)

    def add_mode(
        self,
        title: str
        | list["StatefulBaseRenderer[Any]" | type["StatefulBaseRenderer[Any]"]]
        | type["StatefulBaseRenderer[Any]"]
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
            raise RuntimeError("Unable to start as no GameModes were added.")

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

    def _prepare_container(
        self,
        *,
        device: Device,
        resolver: RuntimeContainer | None,
        render_variant: RendererVariant,
    ) -> RuntimeContainer:
        if resolver is None:
            return build_runtime_container(
                device=device,
                render_variant=render_variant,
            )
        configure_runtime_container(
            container=resolver,
            device=device,
            render_variant=render_variant,
        )
        return resolver

    def _load_components(self) -> GameLoopComponents:
        return self.context_container.resolve(GameLoopComponents)

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
            self.running = self.event_handler.handle_events()
            self._preprocess_setup()
            renderers = self._select_renderers()
            self._one_loop(renderers)
            clock.tick(self.max_fps)
