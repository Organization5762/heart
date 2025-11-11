import random
from dataclasses import dataclass
from enum import StrEnum

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.assets.loader import spritesheet as SpritesheetAsset
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.internal import SwitchStateConsumer
from heart.peripheral.core.manager import PeripheralManager


class LoopPhase(StrEnum):
    START = "start"
    LOOP = "loop"
    END = "end"


# Renderer state snapshot for `SpritesheetLoopRandom`.
@dataclass
class SpritesheetLoopRandomState:
    spritesheet: SpritesheetAsset | None = None
    current_frame: int = 0
    loop_count: int = 0
    phase: LoopPhase = LoopPhase.LOOP
    time_since_last_update: float | None = None
    current_screen: int = 0


# Renders a looping spritesheet on a random screen.
class SpritesheetLoopRandom(
    SwitchStateConsumer, AtomicBaseRenderer[SpritesheetLoopRandomState]
):
    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        sheet_file_path: str,
        metadata_file_path: str,
        screen_count: int,
    ) -> None:
        SwitchStateConsumer.__init__(self)
        self.screen_width, self.screen_height = screen_width, screen_height
        self.screen_count = screen_count
        self.file = sheet_file_path
        frame_data = Loader.load_json(metadata_file_path)
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
        self._initial_phase = (
            LoopPhase.START if len(self.frames[LoopPhase.START]) > 0 else LoopPhase.LOOP
        )

        # TODO: Why is this 30 30 / should we be pulling this from somewhere
        self.x = 30
        self.y = 30

        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        spritesheet = Loader.load_spirtesheet(self.file)
        self.update_state(spritesheet=spritesheet)
        self.bind_switch(peripheral_manager)
        super().initialize(window, clock, peripheral_manager, orientation)

    def __duration_scale_factor(self) -> float:
        current_value = self.get_switch_state().rotation_since_last_button_press
        return current_value / 20.00

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        state = self.state
        current_phase_frames = self.frames[state.phase]
        current_kf = current_phase_frames[state.current_frame]
        kf_duration = current_kf.duration - (
            current_kf.duration
            * self.__duration_scale_factor()
        )
        if state.time_since_last_update is None or state.time_since_last_update > kf_duration:
            next_frame = state.current_frame + 1
            next_screen = state.current_screen
            if next_frame >= len(current_phase_frames):
                next_frame = 0
                next_screen = random.randint(0, self.screen_count - 1)
            self.update_state(
                current_frame=next_frame,
                time_since_last_update=0,
                current_screen=next_screen,
            )
            state = self.state

        spritesheet = state.spritesheet
        if spritesheet is None:
            return

        image = spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(image, (self.screen_width, self.screen_height))
        window.blit(scaled, (state.current_screen * self.screen_width, 0))

        elapsed = (state.time_since_last_update or 0) + clock.get_time()
        self.update_state(time_since_last_update=elapsed)

    def _create_initial_state(self) -> SpritesheetLoopRandomState:
        return SpritesheetLoopRandomState(phase=self._initial_phase)

