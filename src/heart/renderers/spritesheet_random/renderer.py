import logging
import random

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.spritesheet_random.provider import \
    SpritesheetLoopRandomProvider
from heart.renderers.spritesheet_random.state import (
    LoopPhase, SpritesheetLoopRandomState)

logger = logging.getLogger(__name__)


class SpritesheetLoopRandom(StatefulBaseRenderer[SpritesheetLoopRandomState]):
    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        sheet_file_path: str,
        metadata_file_path: str,
        screen_count: int,
        provider: SpritesheetLoopRandomProvider | None = None,
    ) -> None:
        self.screen_width, self.screen_height = screen_width, screen_height
        self.screen_count = screen_count
        self.file = sheet_file_path
        self.frames = {LoopPhase.START: [], LoopPhase.LOOP: [], LoopPhase.END: []}
        frame_data = Loader.load_json(metadata_file_path)
        for key, frame_obj in frame_data["frames"].items():
            frame = frame_obj["frame"]
            parsed_tag, _ = key.split(" ", 1)
            tag = LoopPhase(parsed_tag) if parsed_tag in self.frames else LoopPhase.LOOP
            self.frames[tag].append(
                KeyFrame(
                    (frame["x"], frame["y"], frame["w"], frame["h"]),
                    frame_obj["duration"],
                )
            )
        self._initial_phase = (
            LoopPhase.START if len(self.frames[LoopPhase.START]) > 0 else LoopPhase.LOOP
        )

        self.x = 30
        self.y = 30
        self.provider = provider or SpritesheetLoopRandomProvider(sheet_file_path)

        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

    def __duration_scale_factor(self) -> float:
        current_value = 0
        if self.state.switch_state:
            current_value = self.state.switch_state.rotation_since_last_button_press
        return current_value / 20.00

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
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

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> SpritesheetLoopRandomState:
        return self.provider.create_initial_state(
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
            initial_phase=self._initial_phase,
            update_switch_state=lambda state: self.update_state(switch_state=state),
        )
