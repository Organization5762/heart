from __future__ import annotations

import pygame

from heart.assets.spritesheet import Spritesheet
from heart.runtime.display_context import DisplayContext


class Animation:
    def __init__(self, spritesheet: Spritesheet, width: int) -> None:
        self.spritesheet = spritesheet

        image_size = self.spritesheet.sheet.get_size()
        self.number_of_frames = image_size[0] / width

        self.key_frames = [
            (width * index, 0, width, image_size[1])
            for index in range(int(self.number_of_frames))
        ]
        self.current_frame = 0
        self.ms_since_last_update: float | None = None
        self.ms_per_frame = 25

    def step(self, window: DisplayContext) -> pygame.Surface:
        if (
            self.ms_since_last_update is None
            or self.ms_since_last_update > self.ms_per_frame
        ):
            if self.current_frame >= self.number_of_frames - 1:
                self.current_frame = 0
            else:
                self.current_frame += 1

            self.ms_since_last_update = 0

        image = self.spritesheet.image_at(self.key_frames[self.current_frame])
        self.ms_since_last_update += window.clock.get_time()
        return image
