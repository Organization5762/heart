from dataclasses import dataclass
from functools import cached_property, lru_cache

import pygame
from PIL import Image

from heart.device import Device

import subprocess

def _get_display_resolution():
    result = subprocess.run(
        ["system_profiler", "SPDisplaysDataType"],
        capture_output=True,
        text=True
    )
    
    # find the line with the resolution
    for line in result.stdout.splitlines():
        if "Resolution" in line:
            res = line.split(":")[1].strip()
            parsable = res.replace(" x ", "x").split(" ")[0]
            width, height = map(int, parsable.split("x"))
            aspect_ratio = width / height
            return width, height, aspect_ratio

@dataclass
class LocalScreen(Device):
    width: int
    height: int

    def __post_init__(self) -> None:
        pass
        self.scaled_screen = pygame.display.set_mode(
            (
                self.full_display_size()[0] * self.scale_factor,
                self.full_display_size()[1] * self.scale_factor,
            ),
            pygame.SHOWN,
        )

    def individual_display_size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @cached_property
    def scale_factor(self) -> int:
        width, height, _ = _get_display_resolution()
        current_width , current_height= self.full_display_size()

        result = max(min(width // current_width, height // current_height), 1)
        return int(result / 3)

    def set_image(self, image: Image.Image) -> None:
        assert (
            image.size == self.full_display_size()
        ), f"Image size does not match display size. Image size: {image.size}, Display size: {self.full_display_size()}"

        scaled_image = image.resize(
            (
                self.full_display_size()[0] * self.scale_factor,
                self.full_display_size()[1] * self.scale_factor,
            )
        )

        self.scaled_screen.blit(
            pygame.image.fromstring(
                scaled_image.tobytes(), scaled_image.size, scaled_image.mode
            ),
            (0, 0),
        )
