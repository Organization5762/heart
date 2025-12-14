from __future__ import annotations

from dataclasses import replace

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers.spritesheet.state import (FrameDescription,
                                                       LoopPhase,
                                                       SpritesheetFrames,
                                                       SpritesheetLoopState)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.gamepad.gamepad import Gamepad
from heart.peripheral.gamepad.peripheral_mappings import (BitDoLite2,
                                                          BitDoLite2Bluetooth)
from heart.peripheral.switch import SwitchState
from heart.utilities.env import Configuration


class SpritesheetLoopProvider:
    def __init__(
        self,
        *,
        sheet_file_path: str,
        frames: SpritesheetFrames,
        disable_input: bool,
        boomerang: bool,
        initial_phase: LoopPhase,
    ) -> None:
        self.sheet_file_path = sheet_file_path
        self.frames = frames
        self.disable_input = disable_input
        self.boomerang = boomerang
        self.initial_phase = initial_phase

    @classmethod
    def frames_from_metadata(
        cls, metadata_path: str, boomerang: bool
    ) -> tuple[SpritesheetFrames, LoopPhase]:
        frame_data = Loader.load_json(metadata_path)
        frames = SpritesheetFrames.empty()
        for key in frame_data["frames"]:
            frame_obj = FrameDescription.from_dict(frame_data["frames"][key])
            frame = frame_obj.frame
            parsed_tag, _ = key.split(" ", 1)
            tag = (
                LoopPhase(parsed_tag)
                if parsed_tag in LoopPhase._value2member_map_
                else LoopPhase.LOOP
            )
            frames.by_phase(tag).append(
                KeyFrame((frame.x, frame.y, frame.w, frame.h), frame_obj.duration)
            )
        return frames, (LoopPhase.START if frames.start else LoopPhase.LOOP)

    def initial_state(
        self,
        *,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> SpritesheetLoopState:
        return SpritesheetLoopState(
            phase=self.initial_phase,
            spritesheet=Loader.load_spirtesheet(self.sheet_file_path),
            gamepad=self._configure_gamepad(peripheral_manager),
        )

    def reset_state(self, state: SpritesheetLoopState) -> SpritesheetLoopState:
        return replace(
            state,
            phase=self.initial_phase,
            current_frame=0,
            loop_count=0,
            duration_scale=0.0,
            time_since_last_update=None,
        )

    def handle_switch(
        self, *, state: SpritesheetLoopState, switch_state: SwitchState
    ) -> SpritesheetLoopState:
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
        )

    def advance(
        self,
        *,
        state: SpritesheetLoopState,
        clock: pygame.time.Clock,
    ) -> SpritesheetLoopState:
        state = self._apply_gamepad_input(state)
        current_kf = self.frames.by_phase(state.phase)[state.current_frame]
        kf_duration = self._calculate_duration(
            current_kf.duration, state.duration_scale
        )
        time_since_last_update = state.time_since_last_update or 0
        current_frame = state.current_frame
        loop_count = state.loop_count
        phase = state.phase
        reverse_direction = state.reverse_direction

        if time_since_last_update > kf_duration:
            if self.boomerang and phase == LoopPhase.LOOP:
                if reverse_direction:
                    current_frame -= 1
                else:
                    current_frame += 1
            else:
                current_frame += 1
            time_since_last_update = 0

            if self.boomerang and phase == LoopPhase.LOOP:
                frames = self.frames.by_phase(phase)
                if current_frame >= len(frames) - 1:
                    reverse_direction = True
                    current_frame = len(frames) - 1
                elif current_frame <= 0:
                    reverse_direction = False
                    current_frame = 0
                    loop_count += 1
                    if loop_count >= 3:
                        loop_count = 0
                        if self.frames.end:
                            phase = LoopPhase.END
                            current_frame = 0
                            reverse_direction = False
                        elif self.frames.start:
                            phase = LoopPhase.START
                            current_frame = 0
                            reverse_direction = False
            elif current_frame >= len(self.frames.by_phase(phase)):
                current_frame = 0
                match phase:
                    case LoopPhase.START:
                        phase = LoopPhase.LOOP
                    case LoopPhase.LOOP:
                        if loop_count < 4:
                            loop_count += 1
                        else:
                            loop_count = 0
                            if self.frames.end:
                                phase = LoopPhase.END
                            elif self.frames.start:
                                phase = LoopPhase.START
                    case LoopPhase.END:
                        phase = LoopPhase.START

        elapsed = time_since_last_update + clock.get_time()
        return replace(
            state,
            current_frame=current_frame,
            loop_count=loop_count,
            phase=phase,
            reverse_direction=reverse_direction,
            time_since_last_update=elapsed,
        )

    def _configure_gamepad(self, peripheral_manager: PeripheralManager) -> Gamepad | None:
        if self.disable_input:
            return None
        try:
            return peripheral_manager.get_gamepad()
        except ValueError:
            return None

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

    def _calculate_duration(self, base_duration: int, duration_scale: float) -> float:
        if self.disable_input:
            return base_duration
        return base_duration - (base_duration * duration_scale)
