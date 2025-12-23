from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class RenderImageState:
    base_image: pygame.Surface
    window_size: tuple[int, int]
