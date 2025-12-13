from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class RenderImageState:
    image: pygame.Surface
