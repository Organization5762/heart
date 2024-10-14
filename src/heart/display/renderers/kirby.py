import json
from dataclasses import dataclass

import pygame

from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0


class KirbyFlying(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.initialized = False
        self.current_frame = 0
        self.file = Loader._resolve_path("kirby_sleep_64.png")
        json_path = Loader._resolve_path("kirby_sleep_64.json")
        with open(json_path, "r") as f:
            frame_data = json.load(f)

        self.key_frames = []
        for key in frame_data["frames"]:
            frame = frame_data["frames"][key]["frame"]
            self.key_frames.append(
                KeyFrame((frame["x"], frame["y"], frame["w"], frame["h"]))
            )

        self.time_since_last_update = None
        self.time_between_frames_ms = 75

        self.x = 30
        self.y = 30

    def _initialize(self) -> None:
        self.spritesheet = Loader.load_spirtesheet(self.file)
        self.initialized = True

    def process(self, window, clock) -> None:
        if (
            self.time_since_last_update is None
            or self.time_since_last_update > self.time_between_frames_ms
        ):
            if not self.initialized:
                self._initialize()
            else:
                self.current_frame += 1
                if self.current_frame >= len(self.key_frames):
                    self.current_frame = 0
                self.time_since_last_update = 0

        image = self.spritesheet.image_at(self.key_frames[self.current_frame].frame)
        scaled = pygame.transform.scale(image, (64, 64))
        window.blit(scaled, (0, 0))

        if self.time_since_last_update is None:
            self.time_since_last_update = 0
        self.time_since_last_update += clock.get_time()
