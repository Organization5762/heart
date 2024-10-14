import pygame

from heart.display.color import Color
from heart.display.renderers import BaseRenderer


class RenderColor(BaseRenderer):
    def __init__(self, color: Color) -> None:
        super().__init__()
        self.color = color

    def process(self, window: pygame.Surface, clock: pygame.time.Clock) -> None:
        image = pygame.Surface(window.get_size())
        image.fill(self.color)
        window.blit(image, (0, 0))
