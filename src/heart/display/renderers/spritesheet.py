import json
from dataclasses import dataclass
from enum import Enum

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    duration: int


class LoopPhase(Enum):
    START = "start"
    LOOP = "loop"
    END = "end"


# Searching mode loop.
class SpritesheetLoop(BaseRenderer):
    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        sheet_file_path: str,
        metadata_file_path: str,
    ) -> None:
        super().__init__()
        self.screen_width, self.screen_height = screen_width, screen_height
        self.initialized = False
        self.current_frame = 0
        self.loop_count = 0
        self.file = Loader._resolve_path(sheet_file_path)
        json_path = Loader._resolve_path(metadata_file_path)

        with open(json_path, "r") as f:
            # TODO: Parse this into a dataclass
            frame_data = json.load(f)

        self.start_frames = []
        self.loop_frames = []
        self.end_frames = []
        self.frames = {LoopPhase.START: [], LoopPhase.LOOP: [], LoopPhase.END: []}
        for key in frame_data["frames"]:
            frame_obj = frame_data["frames"][key]
            frame = frame_obj["frame"]
            parsed_tag, _ = key.split(" ", 1)
            if parsed_tag not in self.frames:
                tag = LoopPhase.LOOP
            else:
                tag = LoopPhase(parsed_tag)
            self.frames[tag].append(
                KeyFrame(
                    (frame["x"], frame["y"], frame["w"], frame["h"]),
                    frame_obj["duration"],
                )
            )
        self.phase = LoopPhase.LOOP
        if len(self.frames[LoopPhase.START]) > 0:
            self.phase = LoopPhase.START

        self.time_since_last_update = None

        # TODO: Why is this 30 30 / should we be pulling this from somewhere
        self.x = 30
        self.y = 30

    def _initialize(self) -> None:
        self.spritesheet = Loader.load_spirtesheet(self.file)
        self.initialized = True

    def __duration_scale_factor(self, peripheral_manager: PeripheralManager) -> float:
        current_value = peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        return current_value / 20.00

    def process(self, window: pygame.Surface, clock: pygame.time.Clock, peripheral_manager: PeripheralManager, orientation: Orientation) -> None:
        current_kf = self.frames[self.phase][self.current_frame]
        kf_duration = current_kf.duration - (
            current_kf.duration * self.__duration_scale_factor(peripheral_manager=peripheral_manager)
        )
        if (
            self.time_since_last_update is None
            or self.time_since_last_update > kf_duration
        ):
            if not self.initialized:
                self._initialize()
            else:
                self.current_frame += 1
                self.time_since_last_update = 0
                if self.current_frame >= len(self.frames[self.phase]):
                    self.current_frame = 0
                    match self.phase:
                        case LoopPhase.START:
                            self.phase = LoopPhase.LOOP
                        case LoopPhase.LOOP:
                            if self.loop_count < 4:
                                self.loop_count += 1
                            else:
                                self.loop_count = 0
                                if len(self.frames[LoopPhase.END]) > 0:
                                    self.phase = LoopPhase.END
                                elif len(self.frames[LoopPhase.START]) > 0:
                                    self.phase = LoopPhase.START
                        case LoopPhase.END:
                            self.phase = LoopPhase.START

        image = self.spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(image, (self.screen_width, self.screen_height))
        window.blit(scaled, (0, 0))

        if self.time_since_last_update is None:
            self.time_since_last_update = 0
        self.time_since_last_update += clock.get_time()
