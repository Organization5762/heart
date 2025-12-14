from __future__ import annotations

import random
from dataclasses import replace
from typing import Callable

import pygame

from heart.assets.loader import Loader
from heart.display.models import KeyFrame
from heart.display.renderers.spritesheet_random.state import (
    LoopPhase, SpritesheetLoopRandomState)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState


class SpritesheetLoopRandomProvider:
    def __init__(
        self,
        *,
        screen_width: int,
        screen_height: int,
        sheet_file_path: str,
        metadata_file_path: str,
        screen_count: int,
    ) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.screen_count = screen_count
        self.sheet_file_path = sheet_file_path
        self.frames = self._load_frames(metadata_file_path)
        self.initial_phase = LoopPhase.START if self.frames[LoopPhase.START] else LoopPhase.LOOP

    def initial_state(
        self,
        *,
        peripheral_manager: PeripheralManager,
        set_switch_state: Callable[[SwitchState], None],
    ) -> SpritesheetLoopRandomState:
        source = peripheral_manager.get_main_switch_subscription()
        source.subscribe(
            on_next=set_switch_state,
            on_error=lambda e: print(f"Error Occurred: {e}"),
        )
        return SpritesheetLoopRandomState(
            phase=self.initial_phase,
            spritesheet=Loader.load_spirtesheet(self.sheet_file_path),
            switch_state=None,
        )

    def advance(
        self, *, state: SpritesheetLoopRandomState, clock: pygame.time.Clock
    ) -> SpritesheetLoopRandomState:
        current_frames = self.frames[state.phase]
        current_kf = current_frames[state.current_frame]
        kf_duration = current_kf.duration - (
            current_kf.duration * self._duration_scale_factor(state.switch_state)
        )
        time_since_last_update = state.time_since_last_update or 0
        current_frame = state.current_frame
        current_screen = state.current_screen

        if time_since_last_update > kf_duration:
            next_frame = current_frame + 1
            next_screen = current_screen
            if next_frame >= len(current_frames):
                next_frame = 0
                next_screen = random.randint(0, self.screen_count - 1)
            state = replace(
                state,
                current_frame=next_frame,
                time_since_last_update=0,
                current_screen=next_screen,
            )

        elapsed = (state.time_since_last_update or 0) + clock.get_time()
        return replace(state, time_since_last_update=elapsed)

    def _duration_scale_factor(self, switch_state: SwitchState | None) -> float:
        if switch_state is None:
            return 0
        return switch_state.rotation_since_last_button_press / 20.0

    def _load_frames(self, metadata_file_path: str) -> dict[LoopPhase, list[KeyFrame]]:
        frame_data = Loader.load_json(metadata_file_path)
        frames: dict[LoopPhase, list[KeyFrame]] = {
            LoopPhase.START: [],
            LoopPhase.LOOP: [],
            LoopPhase.END: [],
        }
        for key in frame_data["frames"]:
            frame_obj = frame_data["frames"][key]
            frame = frame_obj["frame"]
            parsed_tag, _ = key.split(" ", 1)
            tag = LoopPhase(parsed_tag) if parsed_tag in LoopPhase._value2member_map_ else LoopPhase.LOOP
            frames[tag].append(
                KeyFrame((frame["x"], frame["y"], frame["w"], frame["h"]), frame_obj["duration"])
            )
        return frames
