from typing import List

from src.heart.display.renderers import BaseRenderer
import pygame
import logging
from PIL import Image

# TODO (lampe): Generic Image Scroller
from src.heart.projects.rgb_display import ImageScroller

logger = logging.getLogger(__name__)

ACTIVE_GAME_LOOP = None

RGB_IMAGE_FORMAT = "RGB"

class GameLoop:
    def __init__(self, width: int, height: int, devices: List[ImageScroller], max_fps: int = 60) -> None:
        self.initalized = False

        self.max_fps = max_fps
        self.renderers: List[BaseRenderer] = []
        self.dimensions = (width, height)
        self.display_mode = pygame.SHOWN
        self.clock = None
        self.screen = None
        self.devices = devices

    @classmethod
    def get_game_loop(cls):
        return ACTIVE_GAME_LOOP
    
    @classmethod
    def set_game_loop(cls, loop: "GameLoop"):
        global ACTIVE_GAME_LOOP
        ACTIVE_GAME_LOOP = loop

    def add_renderer(self, renderer: BaseRenderer):
        self.renderers.append(renderer)
        
    def _initialize(self) -> None:
        if self.get_game_loop() is not None:
            raise Exception("An active GameLoop exists already, please re-use that one")
        
        GameLoop.set_game_loop(self)
        
        logger.info("Initializing Display")
        pygame.init()
        self.screen = pygame.display.set_mode(
            self.dimensions,
            self.display_mode
        )
        self.clock = pygame.time.Clock()
        logger.info("Display Initialized")
        self.initalized = True

    def start(self) -> None:
        if not self.initalized:
            self._initialize()
        self.running = True

        while self.running:
            # pygame.QUIT event means the user clicked X to close your window
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    
            self.__dim_display()
            
            for renderer in self.renderers:
                renderer.process(self.screen, self.clock)

            # TODO: Not sure if this call is necessary
            pygame.display.flip()
            buffer = pygame.image.tostring(self.screen, RGB_IMAGE_FORMAT)
            # Create a PIL image from the string buffer
            image = Image.frombytes(RGB_IMAGE_FORMAT, self.dimensions, buffer)
            for device in self.devices:
                device.set_image(image)
            
            self.clock.tick(self.max_fps)

        pygame.quit()
    
    def __dim_display(self):
        # Default to fully black, so the LEDs will be at lower power
        self.screen.fill("black")