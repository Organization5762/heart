import logging
import math
import os
import random
import time
from enum import StrEnum
from typing import Literal

import pygame
from PIL import Image
from tqdm import tqdm

from heart.display.renderers import BaseRenderer
from heart.input.env import Environment
from heart.input.switch import SwitchSubscriber
from heart.projects.rgb_display import Device

logger = logging.getLogger(__name__)

ACTIVE_GAME_LOOP = None
RGB_IMAGE_FORMAT = "RGB"


class DeviceDisplayMode(StrEnum):
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

    def add_renderer(self, *renderers: BaseRenderer):
        self.renderers.extend(renderers)


class GameLoop:
    def __init__(self, device: Device, max_fps: int = 60) -> None:
        self.initalized = False
        self.device = device

        self.max_fps = max_fps
        self.modes: list[GameMode] = []
        self.display_mode = pygame.SHOWN
        self.clock = None
        self.screen = None

        self.time_last_debugging_press = None

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

    def start(self) -> None:
        if not self.initalized:
            self._initialize()

        if len(self.modes) == 0:
            raise Exception("Unable to start as no GameModes were added.")

        self.running = True

        while self.running:
            self._handle_events()

            self._preprocess_setup()
            renderers = self.active_mode().renderers
            for renderer in tqdm(
                renderers, disable=not Environment.is_profiling_mode()
            ):
                try:
                    renderer.process(self.screen, self.clock)
                except Exception as e:
                    print(e)
                    pass
            # Last renderer dictates the mode
            self._render_out(renderers[-1].device_display_mode)

            self.clock.tick(self.max_fps)

        pygame.quit()

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def _preprocess_setup(self):
        if not Environment.is_pi():
            self.__process_debugging_key_presses()
        self.__dim_display()

    def _render_out(self, device_display_mode: DeviceDisplayMode):
        scaled_surface = pygame.transform.scale(
            self.screen, self.scaled_screen.get_size()
        )
        self.scaled_screen.blit(scaled_surface, (0, 0))

        pygame.display.flip()

        surface_array = pygame.surfarray.array3d(self.screen)
        image = Image.fromarray(
            surface_array.transpose((1, 0, 2)), mode=RGB_IMAGE_FORMAT
        )

        match device_display_mode:
            case DeviceDisplayMode.MIRRORED:
                columns_count, rows_count = self.device.display_count()
                col_size, row_size = self.device.individual_display_size()

                # TODO: This seems conceptually cleaner, but doesn't actually work, because renders place a 64x64 object within the full one
                # and that results in it just squishing this.  It would be nicer if the renderers just had a "pure" screen, and then mirorring resizing etc. could happen outside of their scope
                # (If they are in mirrored mode, full mode should ofc. expose the full canvas)
                # Resize the PyGame image to the size of a single unit
                # image = image.resize(self.device.individual_display_size())

                final_image = Image.new("RGB", self.device.full_display_size())

                # TODO: Unclear if we want mirrored to mean "Mirrored for all displays" or something else
                # Imagine we have a 16 LED cube, where each side has 4, and we want to mirror it.
                # We can handle those more complex device unit configurations later
                for i in range(columns_count):
                    for j in range(rows_count):
                        paste_box = (
                            i * col_size,
                            j * row_size,
                        )
                        final_image.paste(image, box=paste_box)
            case DeviceDisplayMode.FULL:
                # The image just is the full image
                final_image = image

        self.device.set_image(final_image)

    def _initialize(self) -> None:
        if self.get_game_loop() is not None:
            raise Exception("An active GameLoop exists already, please re-use that one")

        GameLoop.set_game_loop(self)
        logger.info("Initializing Display")

        pygame.init()
        full_screen_dimensions = self.device.full_display_size()
        self.screen = pygame.Surface(full_screen_dimensions)
        self.scaled_screen = pygame.display.set_mode(
            (
                full_screen_dimensions[0] * self.device.get_scale_factor(),
                full_screen_dimensions[1] * self.device.get_scale_factor(),
            ),
            self.display_mode,
        )
        self.clock = pygame.time.Clock()
        logger.info("Display Initialized")
        self.initalized = True

    def __dim_display(self):
        # Default to fully black, so the LEDs will be at lower power
        self.screen.fill("black")

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
