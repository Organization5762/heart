import random
from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
import pygame

class Heart(BaseRenderer):
    def __init__(self) -> None:
        pass

    def process(self, window, clock) -> None:
        # TODO: Cache?
        w, h = pygame.display.get_surface().get_size()

