import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager
from heart.display.models import KeyFrame
from heart.assets.loader import Loader


class MarioRenderer(BaseRenderer):
    def __init__(
        self,
        sheet_file_path: str,
        metadata_file_path: str,
      ) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.initialized = False
        self.accel = None
        self.in_loop = False
        self.current_frame = 0
        self.time_since_last_update = None
        self.file = sheet_file_path

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

    def _initialize(self) -> None:
        """Initialize any resources needed for rendering."""
        self.spritesheet = Loader.load_spirtesheet(self.file)
        self.initialized = True

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Process and render the Mario scene.
        
        Args:
            window: The pygame surface to render to
            clock: The pygame clock for timing
            peripheral_manager: Manager for accessing peripheral devices
            orientation: The current device orientation
        """
        if not self.initialized:
            self._initialize()
        
        current_kf = self.frames[self.current_frame]
        kf_duration = current_kf.duration

        if self.in_loop:
            if (
              self.time_since_last_update is None
              or self.time_since_last_update > kf_duration
            ):
                self.current_frame += 1
                self.time_since_last_update = 0

                if self.current_frame >= len(self.frames):
                    self.current_frame = 0
                    self.in_loop = False

            if self.time_since_last_update is None:
                self.time_since_last_update = 0
            self.time_since_last_update += clock.get_time()
        else:
            self.accel = peripheral_manager.get_accelerometer().get_acceleration()
            if self.accel is not None and self.accel.z > 2.0:
                self.in_loop = True
        
        screen_width, screen_height = window.get_size()
        image = self.spritesheet.image_at(current_kf.frame)
        scaled = pygame.transform.scale(
            image, (screen_width, screen_height)
        )
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        window.blit(scaled, (center_x, center_y))
