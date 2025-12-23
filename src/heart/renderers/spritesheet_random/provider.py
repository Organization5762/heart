import random
from dataclasses import replace

import reactivex
from reactivex import operators as ops

from heart.assets.loader import Loader
from heart.display.models import KeyFrame
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.switch import SwitchState
from heart.renderers.spritesheet_random.state import (
    LoopPhase, SpritesheetLoopRandomState)


class SpritesheetLoopRandomProvider(ObservableProvider[SpritesheetLoopRandomState]):
    def __init__(
        self,
        sheet_file_path: str,
        metadata_file_path: str,
        screen_count: int,
    ) -> None:
        self.file = sheet_file_path
        self.screen_count = screen_count
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

        self.initial_phase = (
            LoopPhase.START if len(self.frames[LoopPhase.START]) > 0 else LoopPhase.LOOP
        )

    def initial_state(self) -> SpritesheetLoopRandomState:
        return SpritesheetLoopRandomState(
            phase=self.initial_phase,
            spritesheet=Loader.load_spirtesheet(self.file),
            switch_state=None,
        )

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[SpritesheetLoopRandomState]:
        clocks = peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )
        switches = peripheral_manager.get_main_switch_subscription()
        switch_updates = switches.pipe(
            ops.map(
                lambda switch_state: lambda state: self.handle_switch_state(
                    state, switch_state
                )
            )
        )
        tick_updates = peripheral_manager.game_tick.pipe(
            ops.with_latest_from(clocks),
            ops.map(
                lambda latest: lambda state: self.next_state(
                    state=state,
                    elapsed_ms=latest[1].get_time(),
                )
            ),
        )
        initial_state = self.initial_state()
        return reactivex.merge(switch_updates, tick_updates).pipe(
            ops.scan(lambda state, update: update(state), seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
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
        elapsed_ms: float,
    ) -> SpritesheetLoopRandomState:
        current_phase_frames = self.frames[state.phase]
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
                next_screen = random.randint(0, self.screen_count - 1)
            time_since_last = 0

        time_since_last = (time_since_last or 0) + elapsed_ms
        return replace(
            state,
            current_frame=next_frame,
            time_since_last_update=time_since_last,
            current_screen=next_screen,
        )
