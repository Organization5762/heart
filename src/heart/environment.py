import enum
import inspect
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import numpy as np
import pygame
from PIL import Image

from heart import DeviceDisplayMode
from heart.device import Device, Layout
from heart.firmware_io.constants import BUTTON_LONG_PRESS, BUTTON_PRESS, SWITCH_ROTATION
from heart.navigation import AppController, ComposedRenderer, GameModes, MultiScene
from heart.peripheral.core import events
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

if TYPE_CHECKING:
    from heart.display.renderers import BaseRenderer

logger = get_logger(__name__)

ACTIVE_GAME_LOOP = None
RGBA_IMAGE_FORMAT = "RGBA"


class RendererVariant(enum.Enum):
    BINARY = "BINARY"
    ITERATIVE = "ITERATIVE"
    # TODO: Add more


class GameLoop:
    def __init__(
        self,
        device: Device,
        peripheral_manager: PeripheralManager,
        max_fps: int = 60,
        render_variant: RendererVariant = RendererVariant.ITERATIVE,
    ) -> None:
        self.initalized = False
        self.device = device
        self.peripheral_manager = peripheral_manager

        self.max_fps = max_fps
        self.app_controller = AppController()
        self.clock = None
        self.screen = None
        self.renderer_variant = render_variant

        # jank slide animation state machine
        self.mode_change = (0, 0)
        self.sliding = False
        self._last_mode_offset = 0
        self._last_offset_on_change = 0
        self._current_offset_on_change = 0
        self.renderers_cache = None

        self.time_last_debugging_press = None

        self._active_mode_index = 0
        self._key_pressed_last_frame = defaultdict(lambda: False)

        pygame.display.set_mode(
            (
                device.full_display_size()[0] * device.scale_factor,
                device.full_display_size()[1] * device.scale_factor,
            ),
            pygame.SHOWN,
        )

    def add_mode(self) -> ComposedRenderer:
        return self.app_controller.add_mode()

    def add_scene(self) -> MultiScene:
        return self.app_controller.add_scene()

    @classmethod
    def get_game_loop(cls):
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

        self.running = True
        logger.info("Entering main loop.")

        while self.running:
            self._handle_events()
            self._preprocess_setup()
            renderers = self.app_controller.get_renderers(
                peripheral_manager=self.peripheral_manager
            )
            self._one_loop(renderers)
            self.clock.tick(self.max_fps)

        pygame.quit()

    def process_renderer(self, renderer: "BaseRenderer") -> pygame.Surface | None:
        try:
            match renderer.device_display_mode:
                case DeviceDisplayMode.FULL:
                    # The screen is the full size of the device
                    screen = pygame.Surface(
                        self.device.full_display_size(), pygame.SRCALPHA
                    )
                case DeviceDisplayMode.MIRRORED:
                    # The screen is the full size of the device
                    screen = pygame.Surface(
                        self.device.individual_display_size(), pygame.SRCALPHA
                    )

            # Process the screen

            kwargs = {
                "window": screen,
                "clock": self.clock,
                "peripheral_manager": self.peripheral_manager,
            }
            # check if process function takes a `orientation` argument
            if inspect.signature(renderer.process).parameters.get("orientation"):
                kwargs["orientation"] = self.device.orientation

            if self.sliding:
                renderer.process_with_slide(**kwargs)
            else:
                renderer.process(**kwargs)

            match renderer.device_display_mode:
                case DeviceDisplayMode.MIRRORED:
                    layout: Layout = self.device.orientation.layout
                    screen = self._tile_surface(
                        screen=screen, rows=layout.rows, cols=layout.columns
                    )

                case DeviceDisplayMode.FULL:
                    pass
            return screen
        except Exception as e:
            logger.error(f"Error processing renderer: {e}", exc_info=True)
            return None

    def __finalize_rendering(self, screen: pygame.Surface) -> Image.Image:
        # TODO: This operation will be slow.
        image = pygame.surfarray.pixels3d(screen)
        alpha = pygame.surfarray.pixels_alpha(screen)
        image = np.dstack((image, alpha))
        image = np.transpose(image, (1, 0, 2))
        image = Image.fromarray(image, RGBA_IMAGE_FORMAT)
        return image

    def _tile_surface(
        self, screen: pygame.Surface, rows: int, cols: int
    ) -> pygame.Surface:
        tile_width, tile_height = screen.get_size()
        tiled_surface = pygame.Surface(
            (tile_width * cols, tile_height * rows), pygame.SRCALPHA
        )

        for row in range(rows):
            for col in range(cols):
                dest_pos = (col * tile_width, row * tile_height)
                tiled_surface.blit(screen, dest_pos)

        return tiled_surface

    def merge_surfaces(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        # Ensure both surfaces are the same size
        assert (
            surface1.get_size() == surface2.get_size()
        ), "Surfaces must be the same size to merge."
        surface1.blit(surface2, (0, 0))
        return surface1

    def _render_surface_iterative(
        self, renderers: list["BaseRenderer"]
    ) -> pygame.Surface | None:
        base = None
        for renderer in renderers:
            surface = self.process_renderer(renderer)
            if base is None:
                base = surface
            else:
                base = self.merge_surfaces(base, surface)
        return base

    def _render_surfaces_binary(
        self, renderers: list["BaseRenderer"]
    ) -> pygame.Surface | None:
        with ThreadPoolExecutor() as executor:
            surfaces: list[pygame.Surface] = [
                i
                for i in list(executor.map(self.process_renderer, renderers))
                if i is not None
            ]

            # Iteratively merge surfaces until only one remains
            while len(surfaces) > 1:
                pairs = []
                # Create pairs of adjacent surfaces
                for i in range(0, len(surfaces) - 1, 2):
                    pairs.append((surfaces[i], surfaces[i + 1]))

                # Merge pairs in parallel
                merged_surfaces = list(
                    executor.map(lambda p: self.merge_surfaces(*p), pairs)
                )

                # If there's an odd surface out, append it to the merged list
                if len(surfaces) % 2 == 1:
                    merged_surfaces.append(surfaces[-1])

                # Update the surfaces list for the next iteration
                surfaces = merged_surfaces

        if surfaces:
            return surfaces[0]
        else:
            return None

    def _render_fn(self, override_renderer_variant: RendererVariant | None):
        variant = override_renderer_variant or self.renderer_variant
        match variant:
            case RendererVariant.BINARY:
                return self._render_surfaces_binary
            case RendererVariant.ITERATIVE:
                return self._render_surface_iterative

    def _one_loop(
        self,
        renderers: list["BaseRenderer"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> None:
        # Add border in select mode
        result: pygame.Surface | None = self._render_fn(override_renderer_variant)(
            renderers
        )
        image = self.__finalize_rendering(result) if result else None
        if image is not None:
            bytes = image.tobytes()
            surface = pygame.image.frombytes(bytes, image.size, image.mode)
            self.screen.blit(surface, (0, 0))

        if len(renderers) > 0:
            pygame.display.flip()
            # Convert screen to PIL Image
            image = pygame.surfarray.array3d(self.screen)
            image = np.transpose(image, (1, 0, 2))
            image = Image.fromarray(image)
            self.device.set_image(image)

    def _handle_events(self) -> None:
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == events.REQUEST_JOYSTICK_MODULE_RESET:
                    print("resetting joystick module")
                    pygame.joystick.quit()
                    pygame.joystick.init()
        except SystemError:
            # (clem): gamepad shit is weird and can randomly put caught segfault
            #   events on queue, I see allusions to this online, people say
            #   try pygame-ce instead
            print("SystemError: Encountered segfaulted event")

    def _preprocess_setup(self):
        self.__dim_display()

    def __set_singleton(self) -> None:
        if self.get_game_loop() is not None:
            raise Exception("An active GameLoop exists already, please re-use that one")

        GameLoop.set_game_loop(self)

    def _initialize_screen(self) -> None:
        pygame.init()
        self.screen = pygame.Surface(self.device.full_display_size(), pygame.HIDDEN)
        self.clock = pygame.time.Clock()

    def _initialize_peripherals(self) -> None:
        logger.info("Attempting to detect attached peripherals")
        self.peripheral_manager.detect()
        logger.info(
            f"Detected attached peripherals - found {len(self.peripheral_manager.peripheral)}. {self.peripheral_manager.peripheral=}"
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
        self.screen.fill("black")
