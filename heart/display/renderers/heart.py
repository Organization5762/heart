import random
from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
import pygame

class Heart(BaseRenderer):
    def __init__(self) -> None:
        self.image = Loader.load("heart.png")
        self.x = None
        self.y = None

        self.speed = 2

        self.x_dir = random.choice([-1, 1])
        self.y_dir = random.choice([-1, 1])

        self.x_buffer = self.image.get_width()
        self.y_buffer = self.image.get_height()

    def _location(self):
        return (self.x, self.y)

    def process(self, window) -> None:
        # TODO: Cache?
        w, h = pygame.display.get_surface().get_size()

        # Randomly initialize
        if self.x is None:
            self.x = random.randint(0, w)
        if self.y is None:
            self.y = random.randint(0, h)


        # Simple wall collision mechanics
        if self.x + 1 > (w - self.x_buffer) or self.x <= 0:
            self.x_dir = -self.x_dir

        if self.y + 1 > (h - self.y_buffer) or self.y <= 0:
            self.y_dir = -self.y_dir

        # Update coordinates
        self.x += (self.speed * self.x_dir)
        self.y += (self.speed * self.y_dir)

        window.blit(self.image, self._location())