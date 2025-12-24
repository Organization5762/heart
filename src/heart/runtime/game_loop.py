from __future__ import annotations

import enum
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable, Literal, cast

import numpy as np
import pygame
from lagom import Container
from PIL import Image

from heart import DeviceDisplayMode
from heart.device import Device
from heart.device.beats import WebSocket
from heart.navigation import AppController, ComposedRenderer, MultiScene
from heart.peripheral.core import events
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import container
from heart.renderers.internal import FrameAccumulator
from heart.utilities.env import Configuration, RenderMergeStrategy
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

if TYPE_CHECKING:
    from heart.renderers import BaseRenderer, StatefulBaseRenderer

logger = get_logger(__name__)
log_controller = get_logging_controller()

ACTIVE_GAME_LOOP: "GameLoop" | None = None
RGBA_IMAGE_FORMAT: Literal["RGBA"] = "RGBA"

RenderMethod = Callable[[list["StatefulBaseRenderer[Any]"]], pygame.Surface | None]


class RendererVariant(enum.StrEnum):
    BINARY = "BINARY"
    ITERATIVE = "ITERATIVE"
    AUTO = "AUTO"
    # TODO: Add more

    @classmethod
    def parse(cls, value: str) -> "RendererVariant":
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("HEART_RENDER_VARIANT must not be empty")
        try:
            return cls[normalized]
        except KeyError as exc:
            options = ", ".join(variant.name.lower() for variant in cls)
            raise ValueError(
                f"Unknown render variant '{value}'. Expected one of: {options}"
            ) from exc


class GameLoop:
    def __init__(
        self,
        device: Device,
        resolver: Container,
        max_fps: int = 500,
        render_variant: RendererVariant = RendererVariant.ITERATIVE,
    ) -> None:
        self.context_container = resolver
        self.initalized = False
        self.device = device
        self.peripheral_manager = container.resolve(PeripheralManager)

        self.max_fps = max_fps
        self.app_controller = AppController()
        self.clock: pygame.time.Clock | None = None
        self.screen: pygame.Surface | None = None
        self.renderer_variant = render_variant
        binary_method = cast(RenderMethod, self._render_surfaces_binary)
        iterative_method = cast(RenderMethod, self._render_surface_iterative)
        object.__setattr__(self, "_render_surfaces_binary", binary_method)
        object.__setattr__(self, "_render_surface_iterative", iterative_method)
        self._render_dispatch: dict[RendererVariant, RenderMethod] = {
            RendererVariant.BINARY: binary_method,
            RendererVariant.ITERATIVE: iterative_method,
        }
        self._render_executor: ThreadPoolExecutor | None = None

        self._render_queue_depth = 0
        self._renderer_surface_cache: dict[
            tuple[int, DeviceDisplayMode, tuple[int, int]], pygame.Surface
        ] = {}
        self._composite_surface_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._composite_accumulator: FrameAccumulator | None = None

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

        self._last_render_mode = pygame.SHOWN

    def _get_renderer_surface(
        self, renderer: "BaseRenderer | StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        size = self.device.full_display_size()
        if not Configuration.render_screen_cache_enabled():
            return pygame.Surface(size, pygame.SRCALPHA)

        cache_key = (id(renderer), renderer.device_display_mode, size)
        cached = self._renderer_surface_cache.get(cache_key)
        if cached is None:
            cached = pygame.Surface(size, pygame.SRCALPHA)
            self._renderer_surface_cache[cache_key] = cached
        else:
            cached.fill((0, 0, 0, 0))
        return cached

    def _get_composite_surface(self, size: tuple[int, int]) -> pygame.Surface:
        if not Configuration.render_screen_cache_enabled():
            surface = pygame.Surface(size, pygame.SRCALPHA)
            surface.fill((0, 0, 0, 0))
            return surface

        cached = self._composite_surface_cache.get(size)
        if cached is None:
            cached = pygame.Surface(size, pygame.SRCALPHA)
            self._composite_surface_cache[size] = cached
        cached.fill((0, 0, 0, 0))
        return cached

    def _get_composite_accumulator(
        self, surface: pygame.Surface
    ) -> FrameAccumulator:
        if (
            self._composite_accumulator is None
            or self._composite_accumulator.surface is not surface
        ):
            self._composite_accumulator = FrameAccumulator(surface)
        else:
            self._composite_accumulator.reset()
        return self._composite_accumulator

    def _get_render_executor(self) -> ThreadPoolExecutor:
        if self._render_executor is None:
            self._render_executor = ThreadPoolExecutor(
                max_workers=Configuration.render_executor_max_workers()
            )
        return self._render_executor

    def add_mode(
        self,
        title: str | list["StatefulBaseRenderer[Any]"] | "StatefulBaseRenderer[Any]" | None = None,
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
        if not self.initalized:
            logger.info("GameLoop not yet initialized, initializing...")
            self._initialize()
            logger.info("Finished initializing GameLoop.")

        if self.app_controller.is_empty():
            raise Exception("Unable to start as no GameModes were added.")

        # Initialize all renderers

        self.running = True
        logger.info("Entering main loop.")

        self.app_controller.initialize(
            window=self.screen,
            clock=self.clock,
            peripheral_manager=self.peripheral_manager,
            orientation=self.device.orientation,
        )
        if self.clock is None or self.screen is None:
            raise RuntimeError("GameLoop failed to initialize display surfaces")
        clock = self.clock

        # Load the screen
        ws = WebSocket()
        self.peripheral_manager.get_event_bus().subscribe(
            on_next=lambda x: ws.send(kind="peripheral", payload=x)
        )

        try:
            while self.running:
                # Push an event for state that requires game tick
                self.peripheral_manager.game_tick.on_next(True)

                self._handle_events()
                self._preprocess_setup()

                renderers = self._select_renderers()
                self._one_loop(renderers)
                clock.tick(self.max_fps)
        finally:
            if self._render_executor is not None:
                self._render_executor.shutdown(wait=True)
                self._render_executor = None
            pygame.quit()

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.peripheral_manager.window.on_next(self.screen)

    def set_clock(self, clock: pygame.time.Clock) -> None:
        self.clock = clock
        self.peripheral_manager.clock.on_next(self.clock)

    def _select_renderers(self) -> list["StatefulBaseRenderer[Any]"]:
        base_renderers = self.app_controller.get_renderers()
        renderers = list(base_renderers) if base_renderers else []
        return renderers

    def process_renderer(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface | None:
        clock = self.clock
        if clock is None:
            raise RuntimeError("GameLoop clock is not initialized")

        try:
            start_ns = time.perf_counter_ns()
            if self.clock is None:
                raise RuntimeError("GameLoop clock is not initialized")
            clock = self.clock
            if renderer.device_display_mode == DeviceDisplayMode.OPENGL:
                if self._last_render_mode != pygame.OPENGL | pygame.DOUBLEBUF:
                    logger.info("Switching to OPENGL mode")
                    pygame.display.set_mode(
                        (
                            self.device.full_display_size()[0]
                            * self.device.scale_factor,
                            self.device.full_display_size()[1]
                            * self.device.scale_factor,
                        ),
                        pygame.OPENGL | pygame.DOUBLEBUF,
                    )
                self._last_render_mode = pygame.OPENGL | pygame.DOUBLEBUF
                screen = self._get_renderer_surface(renderer)
            else:
                if self._last_render_mode != pygame.SHOWN:
                    logger.info("Switching to SHOWN mode")
                    pygame.display.set_mode(
                        (
                            self.device.full_display_size()[0]
                            * self.device.scale_factor,
                            self.device.full_display_size()[1]
                            * self.device.scale_factor,
                        ),
                        pygame.SHOWN,
                    )
                self._last_render_mode = pygame.SHOWN
                screen = self._get_renderer_surface(renderer)

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

            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
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
                "uses_opengl": renderer.device_display_mode
                == DeviceDisplayMode.OPENGL,
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

            return screen
        except Exception as e:
            logger.error("Error processing renderer: %s", e, exc_info=True)
            return None

    def __finalize_rendering(self, screen: pygame.Surface) -> Image.Image:
        image_bytes = pygame.image.tostring(screen, "RGBA")

        #     # Button Three
        #     ###
        #     if (edge_sw := bluetooth_switch.switch_three()) is not None:
        #         d = edge_sw.get_rotation_since_last_long_button_press()
        #         if d:  # ±10 % per detent
        #             self.edge_thresh = int(
        #                 np.clip(self.edge_thresh * (1.0 + 0.10 * d), 1, 255)
        #             )

        #             # --- fast edge magnitude (same math as before) -----------------------------
        #             lum = (
        #                 0.299 * image_array[..., 0]  # perceptual luminance
        #                 + 0.587 * image_array[..., 1]
        #                 + 0.114 * image_array[..., 2]
        #             ).astype(np.int16)

        #             gx = np.abs(np.roll(lum, -1, 1) - np.roll(lum, 1, 1))
        #             gy = np.abs(np.roll(lum, -1, 0) - np.roll(lum, 1, 0))
        #             edge_mag = gx + gy  # 0‥510

        #             # --- convert to a *soft* alpha mask ----------------------------------------
        #             #   • everything below threshold fades to 0
        #             #   • values above threshold ramp smoothly toward 1
        #             alpha = np.clip(
        #                 (edge_mag.astype(np.float32) - self.edge_thresh)
        #                 / (255 - self.edge_thresh),
        #                 0.0,
        #                 1.0,
        #             )
        #             alpha **= 0.5  # gamma-soften: 0.5 ≈ thicker, lighter lines
        #             alpha = alpha[..., None]  # shape => (H,W,1) for RGB broadcasting

        #             # --- composite: dim base layer, add white edges ----------------------------
        #             base = image_array.astype(np.float32) * 0.75  # 25 % darker background
        #             edges = alpha * 255.0  # white strokes
        #             out = np.clip(base + edges, 0, 255)

        #             image_array[:] = out.astype(np.uint8)

        return Image.frombuffer(
            RGBA_IMAGE_FORMAT,
            screen.get_size(),
            image_bytes,
            "raw",
            RGBA_IMAGE_FORMAT,
            0,
            1,
        )

    def _merge_surfaces_in_place(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        # Ensure both surfaces are the same size
        assert surface1.get_size() == surface2.get_size(), (
            "Surfaces must be the same size to merge."
        )
        surface1.blit(surface2, (0, 0))
        return surface1

    def merge_surfaces(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        return self._merge_surfaces_in_place(surface1, surface2)

    def _compose_surfaces_batched(
        self, surfaces: list[pygame.Surface]
    ) -> pygame.Surface:
        size = surfaces[0].get_size()
        composite = self._get_composite_surface(size)
        accumulator = self._get_composite_accumulator(composite)
        for surface in surfaces:
            accumulator.queue_blit(surface)
        return accumulator.flush(clear=False)

    def _compose_surfaces(
        self, surfaces: list[pygame.Surface]
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        if Configuration.render_merge_strategy() == RenderMergeStrategy.IN_PLACE:
            base = surfaces[0]
            for surface in surfaces[1:]:
                base = self.merge_surfaces(base, surface)
            return base
        return self._compose_surfaces_batched(surfaces)

    def _render_surface_iterative(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._render_queue_depth = len(renderers)
        if Configuration.render_merge_strategy() == RenderMergeStrategy.IN_PLACE:
            base = None
            for renderer in renderers:
                surface = self.process_renderer(renderer)
                if base is None:
                    base = surface
                elif surface is None:
                    continue
                else:
                    base = self.merge_surfaces(base, surface)
            return base

        surfaces: list[pygame.Surface] = []
        for renderer in renderers:
            surface = self.process_renderer(renderer)
            if surface is not None:
                surfaces.append(surface)
        return self._compose_surfaces_batched(surfaces) if surfaces else None

    def _render_surfaces_binary(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        if not renderers:
            return None
        if len(renderers) == 1:
            return self.process_renderer(renderers[0])
        self._render_queue_depth = len(renderers)
        executor = self._get_render_executor()
        surfaces: list[pygame.Surface] = [
            surface
            for surface in executor.map(self.process_renderer, renderers)
            if surface is not None
        ]

        if not surfaces:
            return None
        if Configuration.render_merge_strategy() == RenderMergeStrategy.BATCHED:
            return self._compose_surfaces_batched(surfaces)

        # Iteratively merge surfaces until only one remains
        while len(surfaces) > 1:
            pairs = list(zip(surfaces[0::2], surfaces[1::2]))

            # Merge pairs in parallel
            merged_surfaces = list(
                executor.map(lambda p: self.merge_surfaces(*p), pairs)
            )

            # If there's an odd surface out, append it to the merged list
            if len(surfaces) % 2 == 1:
                merged_surfaces.append(surfaces[-1])

            # Update the surfaces list for the next iteration
            surfaces = merged_surfaces

        return surfaces[0]

    def _resolve_render_variant(
        self,
        renderer_count: int,
        override_renderer_variant: RendererVariant | None,
    ) -> RendererVariant:
        variant = override_renderer_variant or self.renderer_variant
        if variant == RendererVariant.AUTO:
            threshold = Configuration.render_parallel_threshold()
            if threshold > 1 and renderer_count >= threshold:
                return RendererVariant.BINARY
            return RendererVariant.ITERATIVE
        return variant

    def _render_fn(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RenderMethod:
        variant = self._resolve_render_variant(len(renderers), override_renderer_variant)
        return self._render_dispatch.get(
            variant, self._render_dispatch[RendererVariant.ITERATIVE]
        )

    def _one_loop(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> None:
        if self.screen is None:
            raise RuntimeError("GameLoop screen is not initialized")
        # Add border in select mode
        render_fn = self._render_fn(renderers, override_renderer_variant)
        result: pygame.Surface | None = render_fn(renderers)
        render_image = self.__finalize_rendering(result) if result else None
        if result is not None:
            self.screen.blit(result, (0, 0))

        if len(renderers) > 0:
            pygame.display.flip()
            if render_image is not None:
                device_image = (
                    render_image.convert("RGB")
                    if render_image.mode != "RGB"
                    else render_image
                )
                self.device.set_image(device_image)
            else:
                # Fallback to a screen capture if we did not render an image.
                screen_array = pygame.surfarray.array3d(self.screen)
                transposed_array = np.transpose(screen_array, (1, 0, 2))
                pil_image = Image.fromarray(transposed_array)
                self.device.set_image(pil_image)

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
            # (clem): gamepad stuff is weird and can randomly put caught segfault
            # events on queue, I see allusions to this online, people say
            # try pygame-ce instead
            logger.warning("SystemError: Encountered segfaulted event", exc_info=True)

    def _preprocess_setup(self) -> None:
        self.__dim_display()

    def __set_singleton(self) -> None:
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
        self.__set_singleton()
        self._initialize_screen()
        self._initialize_peripherals()
        self.initalized = True

    def __dim_display(self) -> None:
        # Default to fully black, so the LEDs will be at lower power
        if self.screen is not None:
            self.screen.fill("black")
