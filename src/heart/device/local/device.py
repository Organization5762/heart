from dataclasses import dataclass
from functools import cached_property
from typing import Literal, cast

import pygame
from PIL import Image

from heart.device import Device
from heart.device.local.resolution import get_display_resolution


@dataclass
class LocalScreen(Device):
    width: int
    height: int

    def individual_display_size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @cached_property
    def scale_factor(self) -> int:
        width, height, _ = get_display_resolution()
        current_width, current_height = self.full_display_size()

        result = max(min(width // current_width, height // current_height), 1)
        return max(result // 3, 1)

    def setup_screen(self) -> None:
        self.scaled_screen = pygame.display.set_mode(
            (
                self.full_display_size()[0] * self.scale_factor,
                self.full_display_size()[1] * self.scale_factor,
            ),
            pygame.SHOWN
        )


    def set_screen(self, screen: pygame.Surface) -> None:
        # Clear previous pixels
        screen.fill((0, 0, 0))
        screen = pygame.transform.scale(screen, (self.full_display_size()[0] * self.scale_factor, self.full_display_size()[1] * self.scale_factor))

        # self.scaled_screen.blit(
        #     source=screen,
        #     dest=(0, 0),
        # )

    def set_image(self, image: Image.Image) -> None:
        assert image.size == self.full_display_size(), (
            f"Image size does not match display size. Image size: {image.size}, Display size: {self.full_display_size()}"
        )

        self.set_screen(
            screen=pygame.image.fromstring(
                image.tobytes(),
                image.size,
                _normalize_surface_mode(image.mode),
            )
        )



_SURFACE_MODES = {
    "P",
    "RGB",
    "RGBX",
    "RGBA",
    "ARGB",
    "BGRA",
}


def _normalize_surface_mode(mode: str) -> Literal["P", "RGB", "RGBX", "RGBA", "ARGB", "BGRA"]:
    if mode not in _SURFACE_MODES:
        raise ValueError(f"Unsupported image mode for pygame surface: {mode}")
    return cast(Literal["P", "RGB", "RGBX", "RGBA", "ARGB", "BGRA"], mode)
