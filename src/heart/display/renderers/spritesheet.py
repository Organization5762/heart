from dataclasses import dataclass
from enum import Enum
from typing import Any

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.gamepad.peripheral_mappings import BitDoLite2, BitDoLite2Bluetooth
from heart.utilities.env import Configuration


@dataclass
class Size:
    w: int
    h: int


@dataclass
class BoundingBox(Size):
    x: int
    y: int


@dataclass
class FrameDescription:
    frame: BoundingBox
    spriteSourceSize: BoundingBox
    sourceSize: Size
    duration: int
    rotated: bool
    trimmed: bool

    @classmethod
    def from_dict(cls, json_data: dict[str, Any]):
        return cls(
            frame=BoundingBox(
                x=json_data["frame"]["x"],
                y=json_data["frame"]["y"],
                w=json_data["frame"]["w"],
                h=json_data["frame"]["h"],
            ),
            spriteSourceSize=BoundingBox(
                x=json_data["spriteSourceSize"]["x"],
                y=json_data["spriteSourceSize"]["y"],
                w=json_data["spriteSourceSize"]["w"],
                h=json_data["spriteSourceSize"]["h"],
            ),
            sourceSize=Size(
                w=json_data["sourceSize"]["w"],
                h=json_data["sourceSize"]["h"],
            ),
            duration=json_data["duration"],
            rotated=json_data["rotated"],
            trimmed=json_data["trimmed"],
        )


class LoopPhase(Enum):
    START = "start"
    LOOP = "loop"
    END = "end"


# Searching mode loop.
class SpritesheetLoop(BaseRenderer):
    @classmethod
    def from_frame_data(
        cls,
        sheet_file_path: str,
        duration: int,
        image_scale: float = 1.0,
        offset_x: int = 0,
        offset_y: int = 0,
        disable_input: bool = False,
        boomerang: bool = False,
        skip_last_frame: bool = False,
    ):
        sheet = Loader.load_spirtesheet(sheet_file_path)
        size = sheet.get_size()
        # X / 64 = number of frames
        number_of_frames = size[0] // 64
        if skip_last_frame:
            number_of_frames -= 1
        # Create FrameDescriptions
        frame_descriptions = []
        for frame_number in range(number_of_frames):
            x = frame_number * 64
            y = 0
            w = 64
            h = size[1]
            frame_descriptions.append(
                FrameDescription(
                    frame=BoundingBox(x=x, y=y, w=w, h=h),
                    spriteSourceSize=BoundingBox(x=0, y=0, w=w, h=h),
                    sourceSize=Size(w=w, h=h),
                    duration=duration,
                    rotated=False,
                    trimmed=False,
                )
            )

        return cls(
            sheet_file_path=sheet_file_path,
            metadata_file_path=None,
            image_scale=image_scale,
            offset_x=offset_x,
            offset_y=offset_y,
            disable_input=disable_input,
            boomerang=boomerang,
            frame_data=frame_descriptions,
        )

    def __init__(
        self,
        sheet_file_path: str,
        metadata_file_path: str | None = None,
        image_scale: float = 1.0,
        offset_x: int = 0,
        offset_y: int = 0,
        disable_input: bool = False,
        boomerang: bool = False,
        frame_data: list[FrameDescription] | None = None,
    ) -> None:
        super().__init__()
        self.disable_input = disable_input
        self.current_frame = 0
        self.loop_count = 0
        self.file = sheet_file_path
        self.boomerang = boomerang
        self.reverse_direction = False

        assert frame_data is not None or metadata_file_path is not None, (
            "Must provide either frame_data or metadata_file_path"
        )

        self.start_frames = []
        self.loop_frames = []
        self.end_frames = []
        self.frames = {LoopPhase.START: [], LoopPhase.LOOP: [], LoopPhase.END: []}

        if frame_data is None:
            frame_data = Loader.load_json(metadata_file_path)
            for key in frame_data["frames"]:
                frame_obj = FrameDescription.from_dict(frame_data["frames"][key])
                frame = frame_obj.frame
                parsed_tag, _ = key.split(" ", 1)
                if parsed_tag not in self.frames:
                    tag = LoopPhase.LOOP
                else:
                    tag = LoopPhase(parsed_tag)
                self.frames[tag].append(
                    KeyFrame(
                        (
                            frame.x,
                            frame.y,
                            frame.w,
                            frame.h,
                        ),
                        frame_obj.duration,
                    )
                )
        else:
            for frame_description in frame_data:
                self.frames[LoopPhase.LOOP].append(
                    KeyFrame(
                        (
                            frame_description.frame.x,
                            frame_description.frame.y,
                            frame_description.frame.w,
                            frame_description.frame.h,
                        ),
                        frame_description.duration,
                    )
                )

        self.phase = LoopPhase.LOOP
        if len(self.frames[LoopPhase.START]) > 0:
            self.phase = LoopPhase.START

        self.time_since_last_update = None

        self.image_scale = image_scale
        self.offset_x = offset_x
        self.offset_y = offset_y

        self._current_duration_scale_factor = 0.0
        self._last_switch_rot_value = None

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self.spritesheet = Loader.load_spirtesheet(self.file)
        super().initialize(window, clock, peripheral_manager, orientation)

    def reset(self):
        self._current_duration_scale_factor = 0.0

    def _process_input(self, peripheral_manager: PeripheralManager) -> None:
        self._process_switch(peripheral_manager)
        self._process_gamepad(peripheral_manager)

    def _process_switch(self, peripheral_manager: PeripheralManager) -> None:
        current_value = peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        if self._last_switch_rot_value is not None:
            if current_value > self._last_switch_rot_value:
                self._current_duration_scale_factor += 0.05
            elif current_value < self._last_switch_rot_value:
                self._current_duration_scale_factor -= 0.05

        self._last_switch_rot_value = current_value

    def _process_gamepad(self, peripheral_manager: PeripheralManager):
        gamepad = peripheral_manager.get_gamepad()
        mapping = BitDoLite2Bluetooth() if Configuration.is_pi() else BitDoLite2()
        if gamepad.is_connected():
            if gamepad.axis_passed_threshold(mapping.AXIS_R):
                self._current_duration_scale_factor += 0.005
            elif gamepad.axis_passed_threshold(mapping.AXIS_L):
                self._current_duration_scale_factor -= 0.005

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
            self._process_input(peripheral_manager)
            kf_duration = current_kf.duration - (
                current_kf.duration * self._current_duration_scale_factor
            )
        if (
            self.time_since_last_update is None
            or self.time_since_last_update > kf_duration
        ):
            if self.boomerang and self.phase == LoopPhase.LOOP:
                if self.reverse_direction:
                    self.current_frame -= 1
                else:
                    self.current_frame += 1
            else:
                self.current_frame += 1

            self.time_since_last_update = 0

            if self.boomerang and self.phase == LoopPhase.LOOP:
                if self.current_frame >= len(self.frames[self.phase]) - 1:
                    self.reverse_direction = True
                    self.current_frame = len(self.frames[self.phase]) - 1
                elif self.current_frame <= 0:
                    self.reverse_direction = False
                    self.current_frame = 0
                    self.loop_count += 1
                    if self.loop_count >= 4:
                        self.loop_count = 0
                        if len(self.frames[LoopPhase.END]) > 0:
                            self.phase = LoopPhase.END
                            self.current_frame = 0
                            self.reverse_direction = False
                        elif len(self.frames[LoopPhase.START]) > 0:
                            self.phase = LoopPhase.START
                            self.current_frame = 0
                            self.reverse_direction = False
            elif self.current_frame >= len(self.frames[self.phase]):
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
            image, (screen_width * self.image_scale, screen_height * self.image_scale)
        )
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        final_x = center_x + self.offset_x
        final_y = center_y + self.offset_y

        window.blit(scaled, (final_x, final_y))

        if self.time_since_last_update is None:
            self.time_since_last_update = 0
        self.time_since_last_update += clock.get_time()
