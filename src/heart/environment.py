import logging
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import pygame
from PIL import Image

from heart.device import Device, Layout
from heart.input.switch import SwitchSubscriber
from heart.utilities.env import Configuration

if TYPE_CHECKING:
    from heart.display.renderers import BaseRenderer

logger = logging.getLogger(__name__)

ACTIVE_GAME_LOOP = None
RGBA_IMAGE_FORMAT = "RGBA"


class DeviceDisplayMode(Enum):
    MIRRORED = "mirrored"
    FULL = "full"


class GameMode:
    """GameMode represents a mode in the game loop where different renderers can be
    added. Each mode can have multiple renderers that define how the game is displayed.

    Methods:
    - __init__: Initializes a new GameMode instance with an empty list of renderers.
    - add_renderer: Adds a renderer to this game mode

    """

    def __init__(self) -> None:
        self.renderers: list[BaseRenderer] = []

    def add_renderer(self, *renderers: "BaseRenderer"):
        self.renderers.extend(renderers)


class GameLoop:
    def __init__(self, device: Device, max_fps: int = 60) -> None:
        self.initalized = False
        self.device = device

        self.max_fps = max_fps
        self.modes: list[GameMode] = []
        self.clock = None
        self.screen = None

        self.time_last_debugging_press = None

        pygame.display.set_mode(
            (
                device.full_display_size()[0] * device.scale_factor,
                device.full_display_size()[1] * device.scale_factor,
            ),
            pygame.SHOWN,
        )

    @classmethod
    def get_game_loop(cls):
        return ACTIVE_GAME_LOOP

    @classmethod
    def set_game_loop(cls, loop: "GameLoop"):
        global ACTIVE_GAME_LOOP
        ACTIVE_GAME_LOOP = loop

    def add_mode(self):
        new_game_mode = GameMode()
        self.modes.append(new_game_mode)
        return new_game_mode

    def active_mode(self) -> GameMode:
        mode_index = SwitchSubscriber.get().get_button_value() % len(self.modes)
        return self.modes[mode_index]

    def process_renderer(self, renderer: "BaseRenderer") -> Image.Image | None:
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
            renderer.process(screen, self.clock)
            image = pygame.surfarray.pixels3d(screen)
            alpha = pygame.surfarray.pixels_alpha(screen)
            image = np.dstack((image, alpha))
            image = np.transpose(image, (1, 0, 2))
            image = Image.fromarray(image, RGBA_IMAGE_FORMAT)

            match renderer.device_display_mode:
                case DeviceDisplayMode.MIRRORED:
                    layout: Layout = self.device.layout
                    image = image.resize(size=self.device.individual_display_size())
                    final_image_array = np.tile(
                        np.array(image), (layout.rows, layout.columns, 1)
                    )
                    final_image = Image.fromarray(
                        final_image_array, mode=RGBA_IMAGE_FORMAT
                    )

                case DeviceDisplayMode.FULL:
                    final_image = image

            return final_image
        except Exception as e:
            logger.error(f"Error processing renderer: {e}", exc_info=True)
            return None

    def _render_surfaces(self, renderers: list["BaseRenderer"]):
        def merge_surfaces(
            surface1: Image.Image, surface2: Image.Image
        ) -> pygame.Surface:
            # Ensure both surfaces are the same size
            assert (
                surface1.size == surface2.size
            ), "Surfaces must be the same size to merge."
            surface1.paste(surface2, (0, 0), surface2)
            return surface1

        renderers = self.active_mode().renderers
        with ThreadPoolExecutor() as executor:
            surfaces: list[Image.Image] = [
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
                    executor.map(lambda p: merge_surfaces(*p), pairs)
                )

                # If there's an odd surface out, append it to the merged list
                if len(surfaces) % 2 == 1:
                    merged_surfaces.append(surfaces[-1])

                # Update the surfaces list for the next iteration
                surfaces = merged_surfaces

        # Return the final merged surface
        return surfaces[0] if surfaces else None

    def start(self) -> None:
        if not self.initalized:
            self._initialize()

        if len(self.modes) == 0:
            raise Exception("Unable to start as no GameModes were added.")

        self.running = True

        while self.running:
            self._handle_events()

            self._preprocess_setup()
            mode = self.active_mode()
            renderers = mode.renderers
            image = self._render_surfaces(renderers)
            if image is not None:
                bytes = image.tobytes()
                surface = pygame.image.frombytes(
                    bytes, image.size, image.mode
                )
                self.screen.blit(surface, (0, 0))

            if len(renderers) > 0:
                pygame.display.flip()
                # Convert screen to PIL Image
                image = pygame.surfarray.array3d(self.screen)
                image = np.transpose(image, (1, 0, 2))
                image = Image.fromarray(image)
                self.device.set_image(image)
            self.clock.tick(self.max_fps)

        pygame.quit()

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def _preprocess_setup(self):
        if not Configuration.is_pi():
            self.__process_debugging_key_presses()
        self.__dim_display()

    def _initialize(self) -> None:
        if self.get_game_loop() is not None:
            raise Exception("An active GameLoop exists already, please re-use that one")

        GameLoop.set_game_loop(self)
        logger.info("Initializing Display")

        pygame.init()
        self.screen = pygame.Surface(self.device.full_display_size(), pygame.HIDDEN)

        self.clock = pygame.time.Clock()
        logger.info("Display Initialized")
        self.initalized = True

    def __dim_display(self) -> None:
        # Default to fully black, so the LEDs will be at lower power
        self.screen.fill("black")

    # TODO: move this to the device
    def __process_debugging_key_presses(self):
        keys = (
            pygame.key.get_pressed()
        )  # This will give us a dictonary where each key has a value of 1 or 0. Where 1 is pressed and 0 is not pressed.

        current_time = time.time()
        input_lag_seconds = 0.1
        if (
            self.time_last_debugging_press is not None
            and current_time - self.time_last_debugging_press < input_lag_seconds
        ):
            return

        switch = SwitchSubscriber.get().get_switch()
        payload = None
        if keys[pygame.K_LEFT]:
            payload = {"event_type": "rotation", "data": switch.rotational_value - 1}

        if keys[pygame.K_RIGHT]:
            payload = {"event_type": "rotation", "data": switch.rotational_value + 1}

        if keys[pygame.K_UP]:
            payload = {"event_type": "button", "data": 1}

        if payload is not None:
            switch._update_due_to_data(payload)

        self.time_last_debugging_press = current_time

        pygame.display.set_caption(
            f"R: {switch.get_rotational_value()}, NR: {switch.get_rotation_since_last_button_press()}, B: {switch.get_button_value()}"
        )
