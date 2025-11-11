from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import AtomicBaseRenderer
from heart.events.types import AccelerometerVector
from heart.peripheral.core import Input
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

_LOGGER = get_logger(__name__)


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

        self._latest_accelerometer: tuple[float, float, float] | None = None
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.register_event_listener(
            AccelerometerVector.EVENT_TYPE, self._handle_accelerometer_event
        )

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
            vector = self.latest_acceleration()
            if vector is not None and vector[2] > 11.0:  # vibes based constants
                highest_z = max(highest_z, vector[2])
                print(f"highest z: {highest_z}, accel z: {vector[2]}")
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

    def latest_acceleration(self) -> tuple[float, float, float] | None:
        return self._latest_accelerometer

    def _handle_accelerometer_event(self, event: Input) -> None:
        payload = event.data
        if isinstance(payload, AccelerometerVector):
            vector = (payload.x, payload.y, payload.z)
        else:
            try:
                vector = (
                    float(payload["x"]),
                    float(payload["y"]),
                    float(payload["z"]),
                )
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Ignoring malformed accelerometer payload: %s", payload)
                return
        self._latest_accelerometer = vector
