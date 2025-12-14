from __future__ import annotations

from typing import Any

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.spritesheet.provider import \
    SpritesheetLoopProvider
from heart.display.renderers.spritesheet.state import (BoundingBox,
                                                       FrameDescription,
                                                       LoopPhase, Size,
                                                       SpritesheetFrames,
                                                       SpritesheetLoopState)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState


class SpritesheetLoop(AtomicBaseRenderer[SpritesheetLoopState]):
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
    ):
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
        )

    def __init__(
        self,
        sheet_file_path: str,
        metadata_file_path: str | None = None,
        image_scale: float = 1.0,
        offset_x: int = 0,
        offset_y: int = 0,
        disable_input: bool = False,
        boomerang: bool = False,
        frame_data: list[FrameDescription] | None = None,
    ) -> None:
        from heart.assets.loader import Loader

        self.disable_input = disable_input
        self.file = sheet_file_path
        self.boomerang = boomerang

        assert frame_data is not None or metadata_file_path is not None, (
            "Must provide either frame_data or metadata_file_path"
        )

        frames = SpritesheetFrames.empty()
        if frame_data is None:
            frame_data = Loader.load_json(metadata_file_path)
            for key in frame_data["frames"]:
                frame_obj = FrameDescription.from_dict(frame_data["frames"][key])
                frame = frame_obj.frame
                parsed_tag, _ = key.split(" ", 1)
                tag = LoopPhase(parsed_tag) if parsed_tag in LoopPhase._value2member_map_ else LoopPhase.LOOP
                frames.by_phase(tag).append(
                    KeyFrame(
                        (frame.x, frame.y, frame.w, frame.h),
                        frame_obj.duration,
                    )
                )
        else:
            for frame_description in frame_data:
                frames.by_phase(LoopPhase.LOOP).append(
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

        self.image_scale = image_scale
        self.offset_x = offset_x
        self.offset_y = offset_y

        initial_phase = LoopPhase.START if frames.start else LoopPhase.LOOP
        self.provider = SpritesheetLoopProvider(
            sheet_file_path=sheet_file_path,
            frames=frames,
            disable_input=disable_input,
            boomerang=boomerang,
            initial_phase=initial_phase,
        )

        self._frames = frames
        self._initial_phase = initial_phase

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
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )

    def reset(self) -> None:
        self.set_state(self.provider.reset_state(self.state))

    def on_switch_state(self, state: SwitchState) -> None:
        self.set_state(self.provider.handle_switch(state=self.state, switch_state=state))

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.provider.advance(state=self.state, clock=clock)
        self.set_state(state)

        spritesheet = state.spritesheet
        if spritesheet is None:
            return

        screen_width, screen_height = window.get_size()
        current_kf = self._frames.by_phase(state.phase)[state.current_frame]

        image = spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(
            image, (screen_width * self.image_scale, screen_height * self.image_scale)
        )
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        final_x = center_x + self.offset_x
        final_y = center_y + self.offset_y

        window.blit(scaled, (final_x, final_y))


def create_spritesheet_loop(
    peripheral_manager: PeripheralManager,
    *args: Any,
    **kwargs: Any,
) -> SpritesheetLoop:
    renderer = SpritesheetLoop(*args, **kwargs)
    renderer.configure_peripherals(peripheral_manager)
    return renderer
