from __future__ import annotations

from dataclasses import replace
from typing import Any

from heart.assets.loader import Loader
from heart.display.models import KeyFrame
from heart.display.renderers.spritesheet.state import (BoundingBox,
                                                       FrameDescription,
                                                       LoopPhase, Size,
                                                       SpritesheetLoopState)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.gamepad.peripheral_mappings import (BitDoLite2,
                                                          BitDoLite2Bluetooth)
from heart.peripheral.switch import SwitchState
from heart.utilities.env import Configuration


class SpritesheetProvider:
    def __init__(
        self,
        sheet_file_path: str,
        metadata_file_path: str | None = None,
        *,
        image_scale: float = 1.0,
        offset_x: int = 0,
        offset_y: int = 0,
        disable_input: bool = False,
        boomerang: bool = False,
        frame_data: list[FrameDescription] | None = None,
        skip_last_frame: bool = False,
    ) -> None:
        self.disable_input = disable_input
        self.file = sheet_file_path
        self.boomerang = boomerang
        self.image_scale = image_scale
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.skip_last_frame = skip_last_frame

        assert frame_data is not None or metadata_file_path is not None, (
            "Must provide either frame_data or metadata_file_path"
        )

        self.frames: dict[LoopPhase, list[KeyFrame]] = {
            LoopPhase.START: [],
            LoopPhase.LOOP: [],
            LoopPhase.END: [],
        }

        if frame_data is None:
            frame_data = Loader.load_json(metadata_file_path)
            for key in frame_data["frames"]:
                frame_obj = FrameDescription.from_dict(frame_data["frames"][key])
                frame = frame_obj.frame
                parsed_tag, _ = key.split(" ", 1)
                tag = LoopPhase(parsed_tag) if parsed_tag in LoopPhase._value2member_map_ else LoopPhase.LOOP
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

        has_start = len(self.frames[LoopPhase.START]) > 0
        self.initial_phase = LoopPhase.START if has_start else LoopPhase.LOOP

    def _configure_gamepad(self, peripheral_manager: PeripheralManager) -> Any:
        if self.disable_input:
            return None
        try:
            return peripheral_manager.get_gamepad()
        except ValueError:
            return None

    def initial_state(
        self,
        *,
        window: Any,
        clock: Any,
        peripheral_manager: PeripheralManager,
    ) -> SpritesheetLoopState:
        return SpritesheetLoopState(
            phase=self.initial_phase,
            spritesheet=Loader.load_spirtesheet(self.file),
            gamepad=self._configure_gamepad(peripheral_manager),
        )

    def handle_switch(self, state: SpritesheetLoopState, switch_state: SwitchState) -> SpritesheetLoopState:
        if self.disable_input:
            return state

        duration_scale = state.duration_scale
        last_rotation = state.last_switch_rotation or 0
        current_rotation = switch_state.rotation_since_last_button_press
        if current_rotation > last_rotation:
            duration_scale += 0.05
        elif current_rotation < last_rotation:
            duration_scale -= 0.05

        return replace(
            state,
            duration_scale=duration_scale,
            last_switch_rotation=current_rotation,
            switch_state=switch_state,
        )

    def _apply_gamepad_input(self, state: SpritesheetLoopState) -> SpritesheetLoopState:
        if self.disable_input:
            return state

        gamepad = state.gamepad
        if gamepad is None or not gamepad.is_connected():
            return state

        mapping = BitDoLite2Bluetooth() if Configuration.is_pi() else BitDoLite2()
        duration_scale = state.duration_scale
        if gamepad.axis_passed_threshold(mapping.AXIS_R):
            duration_scale += 0.005
        elif gamepad.axis_passed_threshold(mapping.AXIS_L):
            duration_scale -= 0.005

        return replace(state, duration_scale=duration_scale)

    def _next_frame(
        self,
        state: SpritesheetLoopState,
        *,
        kf_duration: float,
        elapsed_ms: float,
    ) -> SpritesheetLoopState:
        current_frame = state.current_frame
        loop_count = state.loop_count
        phase = state.phase
        reverse_direction = state.reverse_direction
        previous_elapsed = state.time_since_last_update
        time_since_last_update = (previous_elapsed or 0) + elapsed_ms

        if previous_elapsed is None or time_since_last_update > kf_duration:
            if self.boomerang and phase == LoopPhase.LOOP:
                current_frame = current_frame - 1 if reverse_direction else current_frame + 1
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
                if phase == LoopPhase.START:
                    phase = LoopPhase.LOOP
                elif phase == LoopPhase.LOOP:
                    if loop_count < 4:
                        loop_count += 1
                    else:
                        loop_count = 0
                        if len(self.frames[LoopPhase.END]) > 0:
                            phase = LoopPhase.END
                        elif len(self.frames[LoopPhase.START]) > 0:
                            phase = LoopPhase.START
                elif phase == LoopPhase.END:
                    phase = LoopPhase.START

        return replace(
            state,
            current_frame=current_frame,
            loop_count=loop_count,
            phase=phase,
            reverse_direction=reverse_direction,
            time_since_last_update=time_since_last_update,
        )

    def advance(self, state: SpritesheetLoopState, *, clock: Any) -> SpritesheetLoopState:
        state = self._apply_gamepad_input(state)

        current_kf = self.frames[state.phase][state.current_frame]
        if self.disable_input:
            kf_duration = current_kf.duration
        else:
            kf_duration = current_kf.duration - (current_kf.duration * state.duration_scale)

        return self._next_frame(state, kf_duration=kf_duration, elapsed_ms=clock.get_time())

    def reset_state(self, state: SpritesheetLoopState) -> SpritesheetLoopState:
        return replace(
            state,
            phase=self.initial_phase,
            current_frame=0,
            loop_count=0,
            duration_scale=0.0,
            time_since_last_update=None,
            reverse_direction=False,
        )

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
    ) -> SpritesheetProvider:
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
            skip_last_frame=skip_last_frame,
        )
