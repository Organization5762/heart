import math
import os
import random
import time
from heart.display.renderers import BaseRenderer
from heart.input.env import Environment
from heart.input.switch import SwitchSubscriber
import pygame
import logging
from PIL import Image
from tqdm import tqdm

logger = logging.getLogger(__name__)

ACTIVE_GAME_LOOP = None

RGB_IMAGE_FORMAT = "RGB"


class GameMode:
    def __init__(self) -> None:
        self.renderers: list[BaseRenderer] = []
        
    def add_renderer(self, renderer: BaseRenderer):
        self.renderers.append(renderer)
    
class GameLoop:
    def __init__(
        self,
        width: int,
        height: int,
        devices: list,
        max_fps: int = 60
    ) -> None:
        self.initalized = False

        self.max_fps = max_fps
        self.modes: list[GameMode] = []
        self.dimensions = (width, height)
        self.display_mode = pygame.SHOWN
        self.clock = None
        self.screen = None
        self.devices = devices
        if len(devices) == 0:
            self.scale_factor = 3
        else:
            self.scale_factor = 1
            
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
            for renderer in tqdm(self.active_mode().renderers, disable=not Environment.is_profiling_mode()):
                try:
                    renderer.process(self.screen, self.clock)
                except:
                    pass
            self._render_out()
            
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
        
    def _render_out(self):
        scaled_surface = pygame.transform.scale(
            self.screen, self.scaled_screen.get_size()
        )
        self.scaled_screen.blit(scaled_surface, (0, 0))

        pygame.display.flip()
        
        surface = self.screen.copy()
        buffer = pygame.image.tostring(surface, RGB_IMAGE_FORMAT)
        # Create a PIL image from the string buffer
        image = Image.frombytes(RGB_IMAGE_FORMAT, self.dimensions, buffer)
        for device in self.devices:
            device.set_image(image)
    
    def _initialize(self) -> None:
        if self.get_game_loop() is not None:
            raise Exception("An active GameLoop exists already, please re-use that one")

        GameLoop.set_game_loop(self)

        logger.info("Initializing Display")
        pygame.init()
        self.screen = pygame.Surface(self.dimensions)
        self.scaled_screen = pygame.display.set_mode(
            (
                self.dimensions[0] * self.scale_factor,
                self.dimensions[1] * self.scale_factor,
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
        keys = pygame.key.get_pressed()  # This will give us a dictonary where each key has a value of 1 or 0. Where 1 is pressed and 0 is not pressed.

        current_time = time.time()
        input_lag_seconds = 0.1
        if self.time_last_debugging_press is not None and current_time - self.time_last_debugging_press < input_lag_seconds:
            return
        
        switch = SwitchSubscriber.get().get_switch()
        payload = None
        if keys[pygame.K_LEFT]:
            payload = {
                "event_type": "rotation",
                "data": switch.rotational_value - 1
            }

        if keys[pygame.K_RIGHT]:
            payload = {
                "event_type": "rotation",
                "data": switch.rotational_value + 1
            }

        if keys[pygame.K_UP]:
            payload = {
                "event_type": "button",
                "data": 1
            }
        
        if payload is not None:
            switch._update_due_to_data(payload)
            
        self.time_last_debugging_press = current_time
            
        pygame.display.set_caption(f"R: {switch.get_rotational_value()}, NR: {switch.get_normalized_rotational_value()}, B: {switch.get_button_value()}")

