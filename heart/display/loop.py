from heart.display.renderers import BaseRenderer
from heart.display.renderers.kirby import KirbyRunning
import pygame
import logging

logger = logging.getLogger(__name__)

class GameLoop:
    def __init__(self, width: int, height: int, renderers: list[BaseRenderer] | None = None, max_fps: int = 60) -> None:
        self.initalized = False

        self.max_fps = max_fps
        self.renderers = renderers or []
        self.dimensions = (width, height)
        self.clock = None
        self.screen = None

    def _initialize(self) -> None:
        logger.info("Initializing Display")
        pygame.init()
        self.screen = pygame.display.set_mode(self.dimensions)
        self.clock = pygame.time.Clock()
        logger.info("Display ")
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

            self.screen.fill("black")

            for renderer in self.renderers:
                renderer.process(self.screen, self.clock)

            # flip() the display to put your work on screen
            pygame.display.flip()

            self.clock.tick(self.max_fps)

        pygame.quit()

if __name__ == "__main__":
    GameLoop(
        512,
        512,
        renderers=[
            KirbyRunning()
        ]
    ).start()