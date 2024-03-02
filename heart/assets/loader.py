import pygame
import os

class Loader:
    @classmethod
    def load(cls, path: str):
        full_path = os.path.join(
            os.path.dirname(__file__),
            path
        )
        return pygame.image.load(full_path)