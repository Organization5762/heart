from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pygame
from lagom import Container
from PIL import Image

from heart.device import Device
from heart.device.beats import WebSocket
from heart.navigation import AppController, ComposedRenderer, MultiScene
from heart.peripheral.core import events
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import container
from heart.runtime.render_pipeline import RendererVariant, RenderPipeline
from heart.utilities.env import Configuration
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

        self.max_fps = max_fps
        self.app_controller = AppController()
        self.clock: pygame.time.Clock | None = None
        self.screen: pygame.Surface | None = None
        self.render_pipeline = RenderPipeline(
            device=device,
            peripheral_manager=self.peripheral_manager,
            render_variant=render_variant,
        )

        # jank slide animation state machine
        self.mode_change: tuple[int, int] = (0, 0)
        self._last_mode_offset = 0
        self._last_offset_on_change = 0
        self._current_offset_on_change = 0
        self.renderers_cache: list["StatefulBaseRenderer[Any]"] | None = None

        self._active_mode_index = 0

        # Lampe controller
        self.feedback_buffer: np.ndarray | None = None
        self.edge_thresh = 1

        pygame.display.set_mode(
            (
                device.full_display_size()[0] * device.scale_factor,
                device.full_display_size()[1] * device.scale_factor,
            ),
            pygame.SHOWN,
        )
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            pygame.event.set_grab(True)

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
        self._configure_peripheral_streaming()

        try:
            self._run_main_loop()
        finally:
            self.render_pipeline.shutdown()
            pygame.quit()

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.peripheral_manager.window.on_next(self.screen)

    def set_clock(self, clock: pygame.time.Clock) -> None:
        self.clock = clock
        self.render_pipeline.set_clock(clock)
        self.peripheral_manager.clock.on_next(self.clock)

    def _select_renderers(self) -> list["StatefulBaseRenderer[Any]"]:
        base_renderers = self.app_controller.get_renderers()
        renderers = list(base_renderers) if base_renderers else []
        return renderers

    def _one_loop(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> None:
        if self.screen is None:
            raise RuntimeError("GameLoop screen is not initialized")
        render_surface = self.render_pipeline.render(
            renderers, override_renderer_variant
        )
        if render_surface is not None:
            self.screen.blit(render_surface, (0, 0))
        self._present_rendered_frame(renderers, render_surface)

    def _handle_events(self) -> None:
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == events.REQUEST_JOYSTICK_MODULE_RESET:
                    logger.info("resetting joystick module")
                    pygame.joystick.quit()
                    pygame.joystick.init()
        except SystemError:
            # (clem): gamepad shit is weird and can randomly put caught segfault
            #   events on queue, I see allusions to this online, people say
            #   try pygame-ce instead
            logger.exception("Encountered segfaulted event")

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
        pygame.init()
        self.set_screen(pygame.Surface(self.device.full_display_size(), pygame.SHOWN))
        self.set_clock(pygame.time.Clock())

    def _initialize_peripherals(self) -> None:
        logger.info("Attempting to detect attached peripherals")
        self.peripheral_manager.detect()
        peripherals = self.peripheral_manager.peripherals
        logger.info(
            "Detected attached peripherals - found %d. peripherals=%s",
            len(peripherals),
            peripherals,
        )
        logger.info("Starting all peripherals")
        self.peripheral_manager.start()

    def _initialize(self) -> None:
        self._set_singleton()
        self._initialize_screen()
        self._initialize_peripherals()
        self.initialized = True

    def _dim_display(self) -> None:
        # Default to fully black, so the LEDs will be at lower power
        if self.screen is not None:
            self.screen.fill("black")

    def _ensure_initialized(self) -> None:
        if self.initialized:
            return
        self._initialize()

    def _initialize_app_controller(self) -> None:
        if self.clock is None or self.screen is None:
            raise RuntimeError("GameLoop failed to initialize display surfaces")
        self.app_controller.initialize(
            window=self.screen,
            clock=self.clock,
            peripheral_manager=self.peripheral_manager,
            orientation=self.device.orientation,
        )

    def _ensure_display_initialized(self) -> None:
        if self.clock is None or self.screen is None:
            raise RuntimeError("GameLoop failed to initialize display surfaces")

    def _configure_peripheral_streaming(self) -> None:
        ws = WebSocket()
        self.peripheral_manager.get_event_bus().subscribe(
            on_next=lambda x: ws.send(kind="peripheral", payload=x)
        )

    def _tick_peripherals(self) -> None:
        self.peripheral_manager.game_tick.on_next(True)

    def _run_main_loop(self) -> None:
        if self.clock is None:
            raise RuntimeError("GameLoop failed to initialize display clock")
        clock = self.clock
        while self.running:
            self._tick_peripherals()
            self._handle_events()
            self._preprocess_setup()
            renderers = self._select_renderers()
            self._one_loop(renderers)
            clock.tick(self.max_fps)

    def _present_rendered_frame(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        render_surface: pygame.Surface | None,
    ) -> None:
        if not renderers:
            return
        pygame.display.flip()
        if render_surface is not None:
            render_image = self.render_pipeline.finalize_rendering(render_surface)
            device_image = (
                render_image.convert("RGB")
                if render_image.mode != "RGB"
                else render_image
            )
            self.device.set_image(device_image)
            return

        if self.screen is None:
            raise RuntimeError("GameLoop screen is not initialized")
        screen_array = pygame.surfarray.array3d(self.screen)
        transposed_array = np.transpose(screen_array, (1, 0, 2))
        pil_image = Image.fromarray(transposed_array)
        self.device.set_image(pil_image)
