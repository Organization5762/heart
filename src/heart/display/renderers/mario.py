from dataclasses import dataclass
from typing import Any

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.sensor import Acceleration
from heart.utilities.logging import get_logger

_LOGGER = get_logger(__name__)


@dataclass
class MarioRendererState:
    spritesheet: Any
    current_frame: int = 0
    time_since_last_update: float | None = None
    in_loop: bool = False
    highest_z: float = 0.0
    latest_acceleration: Acceleration | None = None


class MarioRenderer(AtomicBaseRenderer[MarioRendererState]):
    def __init__(
        self,
        sheet_file_path: str,
        metadata_file_path: str,
    ) -> None:
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

        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> MarioRendererState:
        # TODO: This needs to get access to an accelerometer subscription
        observable = peripheral_manager.get_accelerometer_subscription()

        observable.subscribe(
            on_next=self._handle_accelerometer_event
        )
        

        image = Loader.load_spirtesheet(self.file)
        return MarioRendererState(spritesheet=image)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
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
            vector = self.state.latest_acceleration
            if vector is not None and vector.z > 11.0:  # vibes based constants
                highest_z = max(highest_z, vector.z)
                print(f"highest z: {highest_z}, accel z: {vector.z}")
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
        image = self.state.spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(image, (screen_width, screen_height))
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        window.blit(scaled, (center_x, center_y))

    def _handle_accelerometer_event(self, event: Acceleration | None) -> None:
        if event is None:
            return

        self.update_state(
            latest_acceleration=event
        )