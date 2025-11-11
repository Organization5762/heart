import time
from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class MarioRendererState:
    current_frame: int = 0
    time_since_last_update: float | None = None
    in_loop: bool = False
    highest_z: float = 0.0


class MarioRenderer(AtomicBaseRenderer[MarioRendererState]):
    def __init__(
        self,
        sheet_file_path: str,
        metadata_file_path: str,
    ) -> None:
        self._accel = None
        self.file = sheet_file_path
        self._spritesheet: pygame.Surface | None = None

        frame_data = Loader.load_json(metadata_file_path)
        self.frames = []
        for key in frame_data["frames"]:
            frame_obj = frame_data["frames"][key]
            frame = frame_obj["frame"]
            self.frames.append(
                KeyFrame(
                    (frame["x"], frame["y"], frame["w"], frame["h"]),
                    frame_obj["duration"],
                )
            )

        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def _create_initial_state(self) -> MarioRendererState:
        return MarioRendererState()

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Initialize any resources needed for rendering."""
        self._spritesheet = Loader.load_spirtesheet(self.file)
        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Process and render the Mario scene."""

        if self._spritesheet is None:
            return

        state = self.state
        current_kf = self.frames[state.current_frame]
        current_frame = state.current_frame
        time_since_last_update = state.time_since_last_update
        in_loop = state.in_loop
        highest_z = state.highest_z

        kf_duration = current_kf.duration

        if in_loop:
            if time_since_last_update is None:
                time_since_last_update = 0

            time_since_last_update += clock.get_time()

            if time_since_last_update > kf_duration:
                current_frame += 1
                time_since_last_update = 0

                if current_frame >= len(self.frames):
                    current_frame = 0
                    in_loop = False
        else:
            try:
                self._accel = (
                    peripheral_manager.get_accelerometer().get_acceleration()
                )
            except Exception:
                time.sleep(0.1)
                self._accel = None
            if self._accel is not None and (
                self._accel.z > 11.0
            ):  # vibes based constants found by shaking totem
                highest_z = max(highest_z, self._accel.z)
                print(f"highest z: {highest_z}, accel z: {self._accel.z}")
                in_loop = True
                time_since_last_update = 0

        if not in_loop:
            time_since_last_update = None

        self.update_state(
            current_frame=current_frame,
            time_since_last_update=time_since_last_update,
            in_loop=in_loop,
            highest_z=highest_z,
        )

        screen_width, screen_height = window.get_size()
        image = self._spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(image, (screen_width, screen_height))
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        window.blit(scaled, (center_x, center_y))
