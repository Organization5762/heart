from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState
from heart.renderers import StatefulBaseRenderer
from heart.renderers.spritesheet.provider import SpritesheetProvider
from heart.renderers.spritesheet.state import (FrameDescription,
                                               SpritesheetLoopState)


class SpritesheetLoop(StatefulBaseRenderer[SpritesheetLoopState]):
    def __init__(
        self,
        provider: SpritesheetProvider | str | None = None,
        sheet_file_path: str | None = None,
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
        sheet_argument = sheet_file_path
        if isinstance(provider, SpritesheetProvider):
            resolved_provider = provider
        else:
            if isinstance(provider, str):
                if sheet_argument is not None:
                    raise TypeError(
                        "Provide a SpritesheetProvider or a sheet file path, not both."
                    )
                sheet_argument = provider

            if sheet_argument is None:
                raise TypeError(
                    "A SpritesheetProvider or sheet_file_path must be provided."
                )

            resolved_provider = SpritesheetProvider(
                sheet_file_path=sheet_argument,
                metadata_file_path=metadata_file_path,
                image_scale=image_scale,
                offset_x=offset_x,
                offset_y=offset_y,
                disable_input=disable_input,
                boomerang=boomerang,
                frame_data=frame_data,
                skip_last_frame=skip_last_frame,
            )

        self.provider = resolved_provider
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        super().__init__()

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
    ) -> SpritesheetLoop:
        provider = SpritesheetProvider.from_frame_data(
            sheet_file_path,
            duration,
            image_scale=image_scale,
            offset_x=offset_x,
            offset_y=offset_y,
            disable_input=disable_input,
            boomerang=boomerang,
            skip_last_frame=skip_last_frame,
        )
        return cls(provider)

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
