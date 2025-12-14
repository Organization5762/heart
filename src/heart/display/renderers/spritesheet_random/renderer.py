from dataclasses import replace
from typing import Any

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.spritesheet_random.provider import \
    SpritesheetLoopRandomProvider
from heart.display.renderers.spritesheet_random.state import \
    SpritesheetLoopRandomState
from heart.peripheral.core.manager import PeripheralManager


class SpritesheetLoopRandom(AtomicBaseRenderer[SpritesheetLoopRandomState]):
    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        sheet_file_path: str,
        metadata_file_path: str,
        screen_count: int,
    ) -> None:
        self.provider = SpritesheetLoopRandomProvider(
            screen_width=screen_width,
            screen_height=screen_height,
            sheet_file_path=sheet_file_path,
            metadata_file_path=metadata_file_path,
            screen_count=screen_count,
        )
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        return self.provider.initial_state(
            peripheral_manager=peripheral_manager,
            set_switch_state=self._set_switch_state,
        )

    def _set_switch_state(self, switch_state):
        if self._state is None:
            return
        self.set_state(replace(self.state, switch_state=switch_state))

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation,
    ) -> None:
        state = self.provider.advance(state=self.state, clock=clock)
        self.set_state(state)
        spritesheet = state.spritesheet
        if spritesheet is None:
            return

        current_frames = self.provider.frames[state.phase]
        current_kf = current_frames[state.current_frame]
        image = spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(
            image, (self.provider.screen_width, self.provider.screen_height)
        )
        window.blit(scaled, (state.current_screen * self.provider.screen_width, 0))


def create_spritesheet_loop_random(
    peripheral_manager: PeripheralManager,
    *args: Any,
    **kwargs: Any,
) -> SpritesheetLoopRandom:
    renderer = SpritesheetLoopRandom(*args, **kwargs)
    renderer.configure_peripherals(peripheral_manager)
    return renderer
