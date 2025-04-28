import json
from enum import Enum

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager


class LoopPhase(Enum):
    START = "start"
    LOOP = "loop"
    END = "end"


# Searching mode loop.
class SpritesheetLoop(BaseRenderer):
    def __init__(
        self,
        sheet_file_path: str,
        metadata_file_path: str,
        image_scale: float = 1.0,
        offset_x: int = 0,
        offset_y: int = 0,
        disable_input: bool = False,
    ) -> None:
        super().__init__()
        self.initialized = False
        self.disable_input = disable_input
        self.current_frame = 0
        self.loop_count = 0
        self.file = sheet_file_path
        frame_data = Loader.load_json(metadata_file_path)

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

        self.image_scale = image_scale
        self.offset_x = offset_x
        self.offset_y = offset_y

        self._should_calibrate = True
        self._scale_factor_offset = 0

    def _initialize(self) -> None:
        self.spritesheet = Loader.load_spirtesheet(self.file)
        self.initialized = True

    def _calibrate(self, preripheral_manager: PeripheralManager):
        self._scale_factor_offset = (
            preripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        )
        self._should_calibrate = False

    def __duration_scale_factor(self, peripheral_manager: PeripheralManager) -> float:
        current_value = (
            peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        )
        return (current_value - self._scale_factor_offset) / 20.00

    def reset(self):
        self._should_calibrate = True

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        screen_width, screen_height = window.get_size()
        current_kf = self.frames[self.phase][self.current_frame]
        if self.disable_input:
            kf_duration = current_kf.duration
        else:
            kf_duration = current_kf.duration - (
                current_kf.duration
                * self.__duration_scale_factor(peripheral_manager=peripheral_manager)
            )
        if (
            self.time_since_last_update is None
            or self.time_since_last_update > kf_duration
        ):
            if not self.initialized:
                self._initialize()
            if self._should_calibrate:
                self._calibrate(peripheral_manager)
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
        scaled = pygame.transform.scale(
            image,
            (
                screen_width * self.image_scale,
                screen_height * self.image_scale
            )
        )
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        final_x = center_x + self.offset_x
        final_y = center_y + self.offset_y

        window.blit(scaled, (final_x, final_y))

        if self.time_since_last_update is None:
            self.time_since_last_update = 0
        self.time_since_last_update += clock.get_time()
