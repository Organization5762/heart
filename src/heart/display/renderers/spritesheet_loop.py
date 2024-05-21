import json
from dataclasses import dataclass
import pygame

from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
from heart.input.switch import SwitchSubscriber

@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    duration: int


# Searching mode loop.
class SpritesheetLoop(BaseRenderer):
    def __init__(self, screen_width: int, screen_height: int, sheet_file_path: str, metadata_file_path: str) -> None:
        self.screen_width, self.screen_height = screen_width, screen_height
        self.initialized = False
        self.current_frame = 0
        self.loop_count = 0
        self.file = Loader._resolve_path(sheet_file_path)
        json_path = Loader._resolve_path(metadata_file_path)
        
        with open(json_path, 'r') as f:
            frame_data = json.load(f)

        self.start_frames = []
        self.loop_frames = []
        self.end_frames = []
        self.frames = {
            "start": [],
            "loop": [],
            "end": []
        }
        for key in frame_data["frames"]:
            frame_obj = frame_data["frames"][key]
            frame = frame_obj["frame"]
            tag, _ = key.split(' ', 1)
            if tag not in self.frames:
                tag = "loop"
            self.frames[tag].append(KeyFrame(
                (frame["x"], frame["y"], frame["w"], frame["h"]),
                frame_obj["duration"]
            ))
        self.phase = "loop"
        if len(self.frames["start"]) > 0:
            self.phase = "start"

        self.time_since_last_update = None

        self.x = 30
        self.y = 30

    def _initialize(self) -> None:
        self.spritesheet = Loader.load_spirtesheet(self.file)
        self.initialized = True
        
    def __duration_scale_factor(self):
        current_value = SwitchSubscriber.get().get_normalized_rotational_value()
        return current_value / 20.00
        
    def process(self, window, clock) -> None:
        current_kf = self.frames[self.phase][self.current_frame]
        kf_duration = current_kf.duration + (current_kf.duration * self.__duration_scale_factor())
        if self.time_since_last_update is None or self.time_since_last_update > kf_duration:
            if not self.initialized:
                self._initialize()
            else:
                self.current_frame += 1
                self.time_since_last_update = 0
                if self.current_frame >= len(self.frames[self.phase]):
                    self.current_frame = 0
                    match self.phase:
                        case "start":
                            self.phase = "loop"
                        case "loop":
                            if self.loop_count < 4:
                                self.loop_count += 1
                            else:
                                self.loop_count = 0
                                if len(self.frames["end"]) > 0:
                                    self.phase = "end"
                                elif len(self.frames["start"]) > 0:
                                    self.phase = "start"
                        case "end":
                            self.phase = "start"

        image = self.spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(image, (self.screen_width, self.screen_height))
        window.blit(scaled, (0, 0))

        if self.time_since_last_update is None:
            self.time_since_last_update = 0
        self.time_since_last_update += clock.get_time()
