from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

import numpy as np
import pygame

from heart import DeviceDisplayMode
from heart.device import Device
from heart.navigation import ComposedRenderer, MultiScene
from heart.runtime.container.initialize import (build_runtime_container,
                                                configure_runtime_container)
from heart.runtime.display_context import DisplayContext
from heart.runtime.game_loop.components import GameLoopComponents
from heart.runtime.rendering.pacing import RenderLoopPacer
from heart.runtime.rendering.pipeline import RendererVariant
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import shutdown

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer
    from heart.runtime.container import RuntimeContainer

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
        self.components = self._load_components()
        self._render_pacer = self.context_container.resolve(RenderLoopPacer)

        # Lampe controller
        self.feedback_buffer: np.ndarray | None = None
        self.edge_thresh = EDGE_THRESHOLD
        self.components.display.initialize()

    def _one_loop(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ):
        render_result = self.components.render_pipeline.render_with_plan(
            renderers=renderers,
        )
        render_surface = render_result.surface
        if render_surface is not None:
            self._apply_post_processors(render_surface)
            self.components.display.blit(render_surface, (0, 0))
            pygame.display.flip()

    def _apply_post_processors(self, surface: pygame.Surface) -> None:
        post_processors = self.components.app_controller.get_post_processors()
        if not post_processors:
            return
        post_context = DisplayContext(
            device=self.device,
            screen=surface,
            clock=self.components.display.clock,
            last_render_mode=self.components.display.last_render_mode,
        )
        for renderer in post_processors:
            if not renderer.initialized:
                renderer.initialize(
                    window=post_context,
                    peripheral_manager=self.components.peripheral_manager,
                    orientation=self.device.orientation,
                )
            renderer._internal_process(
                window=post_context,
                peripheral_manager=self.components.peripheral_manager,
                orientation=self.device.orientation,
            )

    def resolve(self, dependency: type[DependencyT]) -> DependencyT:
        return self.context_container.resolve(dependency)

    def compose(
        self,
        renderers: list["StatefulBaseRenderer[Any]" | type["StatefulBaseRenderer[Any]"]],
    ) -> ComposedRenderer:
        result = self.context_container.resolve(ComposedRenderer)
        result.add_renderer(*renderers)
        return result

    def add_mode(
        self,
        title: str
        | list["StatefulBaseRenderer[Any]" | type["StatefulBaseRenderer[Any]"]]
        | type["StatefulBaseRenderer[Any]"]
        | "StatefulBaseRenderer[Any]"
        | None = None,
    ) -> ComposedRenderer:
        return self.components.app_controller.add_mode(title=title)

    def add_scene(self) -> MultiScene:
        return self.components.app_controller.add_scene()

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

        if self.components.app_controller.is_empty():
            raise RuntimeError("Unable to start as no GameModes were added.")

        # Initialize all renderers

        self.running = True
        logger.info("Entering main loop.")

        logger.info("Initializing app controller.")
        self._initialize_app_controller()
        logger.info("Ensuring display is initialized.")
        self._ensure_display_initialized()
        logger.info("Configuring streaming.")
        self.components.peripheral_runtime.configure_streaming()

        try:
            self._run_main_loop()
        finally:
            logger.info("Shutting down GameLoop.")

            # SHut down the IO threads
            shutdown.on_next(True)
            shutdown.on_completed()
            shutdown.dispose()

            self.components.render_pipeline.shutdown()
            pygame.quit()

    def set_screen(self, screen: pygame.Surface) -> None:
        self.components.display.set_screen(screen)
        pygame.display.flip()
        self.components.peripheral_manager.window.on_next(self.components.display.screen)

    def set_clock(self, clock: pygame.time.Clock) -> None:
        self.components.display.set_clock(clock)
        self.components.render_pipeline.set_clock(clock)
        self.components.peripheral_manager.clock.on_next(self.components.display.clock)

    @property
    def screen(self) -> pygame.Surface | None:
        return self.components.display.screen

    @property
    def clock(self) -> pygame.time.Clock | None:
        return self.components.display.clock

    def _select_renderers(self) -> list["StatefulBaseRenderer[Any]"]:
        base_renderers = self.components.app_controller.get_renderers()
        renderers = list(base_renderers) if base_renderers else []
        return renderers

    def _resolve_display_mode(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> DeviceDisplayMode:
        if any(
            renderer.device_display_mode == DeviceDisplayMode.OPENGL
            for renderer in renderers
        ):
            return DeviceDisplayMode.OPENGL
        if any(
            renderer.device_display_mode == DeviceDisplayMode.FULL
            for renderer in renderers
        ):
            return DeviceDisplayMode.FULL
        return DeviceDisplayMode.MIRRORED

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
        self.set_screen(self.components.display.screen)
        self.set_clock(self.components.display.clock)

    def _initialize(self) -> None:
        self._set_singleton()
        self._initialize_screen()
        self.components.peripheral_runtime.detect_and_start()
        self.initialized = True

    def _dim_display(self) -> None:
        # Default to fully black, so the LEDs will be at lower power
        if self.components.display.screen is not None:
            self.components.display.screen.fill("black")

    def _ensure_initialized(self) -> None:
        if self.initialized:
            return
        self._initialize()

    def _initialize_app_controller(self) -> None:
        self.components.display.ensure_initialized()
        logger.info("Initializing app controller components.")
        self.components.app_controller.initialize(
            window=self.components.display,
            peripheral_manager=self.components.peripheral_manager,
            orientation=self.device.orientation,
        )

    def _ensure_display_initialized(self) -> None:
        self.components.display.ensure_initialized()

    def _run_main_loop(self) -> None:
        if self.components.display.clock is None:
            raise RuntimeError("GameLoop failed to initialize display clock")
        while self.running:
            self.components.peripheral_runtime.tick()
            self.running = self.components.event_handler.handle_events()
            self._preprocess_setup()  # can't dim display each time
            renderers = self._select_renderers()
            self.components.display.configure_window(self._resolve_display_mode(renderers))

            self._one_loop(renderers=renderers)
            # self._render_pacer.pace(render_start, 20)

            self.components.display.clock.tick(self.max_fps)

            self.components.peripheral_runtime.tick()
            self.components.peripheral_manager.clock.on_next(self.components.display.clock)
