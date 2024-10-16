from dataclasses import dataclass

import pygame
from PIL import Image

from heart.device import Device, Layout


@dataclass
class LocalScreen(Device):
    width: int
    height: int

    def __post_init__(self) -> None:
        pass
        self.scaled_screen = pygame.display.set_mode(
            (
                self.full_display_size()[0] * self.get_scale_factor(),
                self.full_display_size()[1] * self.get_scale_factor(),
            ),
            pygame.SHOWN,
        )

    def individual_display_size(self) -> tuple[int, int]:
        return (self.width, self.height)

    def get_scale_factor(self) -> int:
        return 5

    def set_image(self, image: Image.Image) -> None:
        assert (
            image.size == self.full_display_size()
        ), f"Image size does not match display size. Image size: {image.size}, Display size: {self.full_display_size()}"

        scaled_image = image.resize(
            (
                self.full_display_size()[0] * self.get_scale_factor(),
                self.full_display_size()[1] * self.get_scale_factor(),
            )
        )

        self.scaled_screen.blit(
            pygame.image.fromstring(
                scaled_image.tobytes(), scaled_image.size, scaled_image.mode
            ),
            (0, 0),
        )
