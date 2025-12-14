from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.spritesheet.provider import SpritesheetProvider
from heart.display.renderers.spritesheet.state import SpritesheetLoopState
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState


class SpritesheetLoop(AtomicBaseRenderer[SpritesheetLoopState]):
    def __init__(self, provider: SpritesheetProvider) -> None:
        self.provider = provider
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        super().__init__()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> SpritesheetLoopState:
        return self.provider.initial_state(
            window=window, clock=clock, peripheral_manager=peripheral_manager
        )

    def on_switch_state(self, state: SwitchState) -> None:
        self.set_state(self.provider.handle_switch(self.state, state))

    def reset(self) -> None:
        super().reset()
        self.set_state(self.provider.reset_state(self.state))

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.provider.advance(self.state, clock=clock)
        self.set_state(state)

        spritesheet = state.spritesheet
        if spritesheet is None:
            return

        screen_width, screen_height = window.get_size()
        current_kf = self.provider.frames[state.phase][state.current_frame]
        image = spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(
            image,
            (
                int(screen_width * self.provider.image_scale),
                int(screen_height * self.provider.image_scale),
            ),
        )
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        final_x = center_x + self.provider.offset_x
        final_y = center_y + self.provider.offset_y

        window.blit(scaled, (final_x, final_y))


def create_spritesheet_loop(
    peripheral_manager: PeripheralManager, *args: object, **kwargs: object
) -> SpritesheetLoop:
    provider = SpritesheetProvider(*args, **kwargs)
    renderer = SpritesheetLoop(provider)
    renderer.configure_peripherals(peripheral_manager)
    return renderer
