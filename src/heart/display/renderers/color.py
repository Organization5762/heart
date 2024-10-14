from dataclasses import dataclass
from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
import pygame

@dataclass
class KeyFrame:
    frame: tuple[int,int,int,int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0

class RenderColor(BaseRenderer):
    def __init__(self, color: tuple[int, int, int]) -> None:
        for variant in color:
            assert variant >= 0 and variant <= 255, f"Expected all color values to be between 0 and 255. Found {color}"
        self.color = color

    def process(self, window, clock) -> None:
        image = pygame.Surface(window.get_size()) 
        image.fill(self.color) 
        window.blit(image, (0,0))
