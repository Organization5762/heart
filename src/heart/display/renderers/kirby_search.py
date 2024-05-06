import json
from dataclasses import dataclass
import pygame

from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    duration: int


@dataclass
class HeartFrame:
    frame: tuple[int, int, int, int]
    pos: tuple[int, int]


# Searching mode loop.
class KirbySearch(BaseRenderer):
    def __init__(self, screen_width, screen_height) -> None:
        self.screen_width, self.screen_height = screen_width, screen_height
        self.initialized = False
        self.current_frame = 0
        self.heart_count = 0
        heart_pos = [(16, 0), (32, 0), (0, 16), (48, 16), (0, 32), (48, 32), (16, 48), (32, 48)]
        self.phase = "start"
        self.file = Loader._resolve_path("kirby_cell_64.png")
        json_path = Loader._resolve_path("kirby_cell_64.json")
        with open(json_path, 'r') as f:
            frame_data = json.load(f)

        self.frames = {
            "start": [],
            "loop": [],
            "end": []
        }
        for key in frame_data["frames"]:
            frame_obj = frame_data["frames"][key]
            frame = frame_obj["frame"]
            tag, _ = key.split(' ', 1)
            self.frames[tag].append(KeyFrame(
                (frame["x"], frame["y"], frame["w"], frame["h"]),
                frame_obj["duration"]
            ))

        self.heart_file = Loader._resolve_path("heart_16.png")
        heart_json = Loader._resolve_path("heart_16.json")
        with open(heart_json, 'r') as f:
            heart_data = json.load(f)

        self.heart_frames = []
        idx = 0
        for key in heart_data["frames"]:
            frame = heart_data["frames"][key]["frame"]
            self.heart_frames.append(HeartFrame(
                (frame["x"], frame["y"], frame["w"], frame["h"]),
                heart_pos[int(idx)]
            ))
            idx += 1

        self.time_since_last_update = None

        self.x = 30
        self.y = 30

    def _initialize(self) -> None:
        self.spritesheet = Loader.load_spirtesheet(self.file)
        self.heart_sprite = Loader.load_spirtesheet(self.heart_file)
        self.initialized = True

    def process(self, window, clock) -> None:
        current_kf = self.frames[self.phase][self.current_frame]
        if self.time_since_last_update is None or self.time_since_last_update > current_kf.duration:
            if not self.initialized:
                self._initialize()
            else:
                self.current_frame += 1
                if self.current_frame >= len(self.frames[self.phase]):
                    self.phase = "loop"
                    self.current_frame = 0
                    if self.heart_count < len(self.heart_frames):
                        self.heart_count += 1
                    else:
                        self.heart_count = 0
                        self.phase = "start"
                self.time_since_last_update = 0

        # Rendering hearts
        for i in range(0, self.heart_count):
            heart_frame = self.heart_frames[i]
            heart_image = self.heart_sprite.image_at(heart_frame.frame)
            heart_scaled = pygame.transform.scale(heart_image, (self.screen_width / 4, self.screen_height / 4))
            scale_factor = self.screen_width / 64
            xy = (heart_frame.pos[0]*scale_factor, heart_frame.pos[1]*scale_factor)
            window.blit(heart_scaled, xy)

        # Rendering searching kirby
        image = self.spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(image, (self.screen_width, self.screen_height))
        window.blit(scaled, (0, 0))

        if self.time_since_last_update is None:
            self.time_since_last_update = 0
        self.time_since_last_update += clock.get_time()
