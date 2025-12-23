import logging
import random
from collections.abc import Callable, Sequence
from dataclasses import replace

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState
from heart.renderers.spritesheet_random.state import (
    LoopPhase, SpritesheetLoopRandomState)

logger = logging.getLogger(__name__)


class SpritesheetLoopRandomProvider:
    def __init__(self, sheet_file_path: str) -> None:
        self.file = sheet_file_path

    def create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
        initial_phase: LoopPhase,
        update_switch_state: Callable[[SwitchState | None], None],
    ) -> SpritesheetLoopRandomState:
        def new_switch_state(value: SwitchState | None) -> None:
            update_switch_state(value)

        source = peripheral_manager.get_main_switch_subscription()
        source.subscribe(
            on_next=new_switch_state,
            on_error=lambda exc: logger.error("Error Occurred: %s", exc),
        )
        return SpritesheetLoopRandomState(
            phase=initial_phase,
            spritesheet=Loader.load_spirtesheet(self.file),
            switch_state=None,
        )

    def handle_switch_state(
        self,
        state: SpritesheetLoopRandomState,
        switch_state: SwitchState | None,
    ) -> SpritesheetLoopRandomState:
        return replace(state, switch_state=switch_state)

    def duration_scale_factor(self, state: SpritesheetLoopRandomState) -> float:
        current_value = 0
        if state.switch_state:
            current_value = state.switch_state.rotation_since_last_button_press
        return current_value / 20.00

    def next_state(
        self,
        state: SpritesheetLoopRandomState,
        current_phase_frames: Sequence,
        screen_count: int,
        elapsed_ms: float,
    ) -> SpritesheetLoopRandomState:
        current_kf = current_phase_frames[state.current_frame]
        kf_duration = current_kf.duration - (
            current_kf.duration * self.duration_scale_factor(state)
        )
        time_since_last = state.time_since_last_update
        next_frame = state.current_frame
        next_screen = state.current_screen
        if time_since_last is None or time_since_last > kf_duration:
            next_frame = state.current_frame + 1
            if next_frame >= len(current_phase_frames):
                next_frame = 0
                next_screen = random.randint(0, screen_count - 1)
            time_since_last = 0

        time_since_last = (time_since_last or 0) + elapsed_ms
        return replace(
            state,
            current_frame=next_frame,
            time_since_last_update=time_since_last,
            current_screen=next_screen,
        )
