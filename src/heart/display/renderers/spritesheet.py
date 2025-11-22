from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

import pygame

from heart.assets.loader import Loader
from heart.assets.loader import spritesheet as SpritesheetAsset
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.gamepad.gamepad import Gamepad
from heart.peripheral.gamepad.peripheral_mappings import (BitDoLite2,
                                                          BitDoLite2Bluetooth)
from heart.peripheral.switch import SwitchState
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
@dataclass
class SpritesheetLoopState:
    spritesheet: SpritesheetAsset | None = None
    current_frame: int = 0
    loop_count: int = 0
    phase: LoopPhase = LoopPhase.LOOP
    time_since_last_update: float | None = None
    duration_scale: float = 0.0
    last_switch_rotation: float | None = None
    reverse_direction: bool = False
    gamepad: Gamepad | None = None


class SpritesheetLoop(AtomicBaseRenderer[SpritesheetLoopState]):
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
        number_of_frames = size[0] // 64
        if skip_last_frame:
            number_of_frames -= 1
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
        self.disable_input = disable_input
        self.file = sheet_file_path
        self.boomerang = boomerang

        assert frame_data is not None or metadata_file_path is not None, (
            "Must provide either frame_data or metadata_file_path"
        )

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

        self.image_scale = image_scale
        self.offset_x = offset_x
        self.offset_y = offset_y

        self._initial_phase = (
            LoopPhase.START if len(self.frames[LoopPhase.START]) > 0 else LoopPhase.LOOP
        )

        AtomicBaseRenderer.__init__(self)

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
        return SpritesheetLoopState(
            phase=self._initial_phase,
            spritesheet=Loader.load_spirtesheet(self.file),
            gamepad=self.configure_gamepad(peripheral_manager)
        )

    def configure_gamepad(self, peripheral_manager: PeripheralManager) -> None:
        if self.disable_input:
            return
        try:
            gamepad = peripheral_manager.get_gamepad()
        except ValueError:
            gamepad = None
        return gamepad

    def reset(self) -> None:
        self.update_state(phase=self._initial_phase)

    def on_switch_state(self, state: SwitchState) -> None:
        if self.disable_input:
            return

        def _mutate(current: SpritesheetLoopState) -> SpritesheetLoopState:
            duration_scale = current.duration_scale
            last_rotation = current.last_switch_rotation
            current_rotation = state.rotation_since_last_button_press
            if last_rotation is not None:
                if current_rotation > last_rotation:
                    duration_scale += 0.05
                elif current_rotation < last_rotation:
                    duration_scale -= 0.05
            return replace(
                current,
                duration_scale=duration_scale,
                last_switch_rotation=current_rotation,
            )

        self.mutate_state(_mutate)

    def _apply_gamepad_input(self) -> None:
        if self.disable_input:
            return

        gamepad = self.state.gamepad
        if gamepad is None or not gamepad.is_connected():
            return

        mapping = BitDoLite2Bluetooth() if Configuration.is_pi() else BitDoLite2()

        def _mutate(current: SpritesheetLoopState) -> SpritesheetLoopState:
            duration_scale = current.duration_scale
            if gamepad.axis_passed_threshold(mapping.AXIS_R):
                duration_scale += 0.005
            elif gamepad.axis_passed_threshold(mapping.AXIS_L):
                duration_scale -= 0.005
            return replace(current, duration_scale=duration_scale)

        self.mutate_state(_mutate)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state
        spritesheet = state.spritesheet
        if spritesheet is None:
            return

        screen_width, screen_height = window.get_size()
        current_kf = self.frames[state.phase][state.current_frame]

        # TODO: Get from event bus
        if not self.disable_input:
            self._apply_gamepad_input()
            state = self.state

        duration_scale = state.duration_scale
        if self.disable_input:
            kf_duration = current_kf.duration
        else:
            kf_duration = current_kf.duration - (
                current_kf.duration * duration_scale
            )

        current_frame = state.current_frame
        loop_count = state.loop_count
        phase = state.phase
        reverse_direction = state.reverse_direction
        time_since_last_update = state.time_since_last_update

        if time_since_last_update is None or time_since_last_update > kf_duration:
            if self.boomerang and phase == LoopPhase.LOOP:
                if reverse_direction:
                    current_frame -= 1
                else:
                    current_frame += 1
            else:
                current_frame += 1

            time_since_last_update = 0

            if self.boomerang and phase == LoopPhase.LOOP:
                if current_frame >= len(self.frames[phase]) - 1:
                    reverse_direction = True
                    current_frame = len(self.frames[phase]) - 1
                elif current_frame <= 0:
                    reverse_direction = False
                    current_frame = 0
                    loop_count += 1
                    if loop_count >= 4:
                        loop_count = 0
                        if len(self.frames[LoopPhase.END]) > 0:
                            phase = LoopPhase.END
                            current_frame = 0
                            reverse_direction = False
                        elif len(self.frames[LoopPhase.START]) > 0:
                            phase = LoopPhase.START
                            current_frame = 0
                            reverse_direction = False
            elif current_frame >= len(self.frames[phase]):
                current_frame = 0
                match phase:
                    case LoopPhase.START:
                        phase = LoopPhase.LOOP
                    case LoopPhase.LOOP:
                        if loop_count < 4:
                            loop_count += 1
                        else:
                            loop_count = 0
                            if len(self.frames[LoopPhase.END]) > 0:
                                phase = LoopPhase.END
                            elif len(self.frames[LoopPhase.START]) > 0:
                                phase = LoopPhase.START
                    case LoopPhase.END:
                        phase = LoopPhase.START

        image = spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(
            image, (screen_width * self.image_scale, screen_height * self.image_scale)
        )
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        final_x = center_x + self.offset_x
        final_y = center_y + self.offset_y

        window.blit(scaled, (final_x, final_y))

        if time_since_last_update is None:
            time_since_last_update = 0
        time_since_last_update += clock.get_time()

        updated_state = replace(
            state,
            current_frame=current_frame,
            loop_count=loop_count,
            phase=phase,
            reverse_direction=reverse_direction,
            time_since_last_update=time_since_last_update,
        )
        self.set_state(updated_state)


def create_spritesheet_loop(
    peripheral_manager: PeripheralManager,
    *args: Any,
    **kwargs: Any,
) -> SpritesheetLoop:
    renderer = SpritesheetLoop(*args, **kwargs)
    renderer.configure_peripherals(peripheral_manager)
    return renderer
