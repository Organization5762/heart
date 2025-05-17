import time

from pygame import Surface, time

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.display.renderers.max_bpm_screen import MaxBpmScreen
from heart.display.renderers.metadata_screen import MetadataScreen
from heart.peripheral.core.manager import PeripheralManager


class CombinedBpmScreen(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

        # Create both renderers
        self.metadata_screen = MetadataScreen()
        self.max_bpm_screen = MaxBpmScreen()

        # Screen swap timing
        self.metadata_duration_ms = 15000  # 15 seconds
        self.max_bpm_duration_ms = 5000  # 5 seconds

        # Track timing state
        self.elapsed_time_ms = 0
        self.showing_metadata = True

    def process(
        self,
        window: Surface,
        clock: time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # Update elapsed time
        self.elapsed_time_ms += clock.get_time()

        # Determine which screen to show based on timing
        if self.showing_metadata and self.elapsed_time_ms >= self.metadata_duration_ms:
            self.showing_metadata = False
            self.elapsed_time_ms = 0
        elif (
            not self.showing_metadata
            and self.elapsed_time_ms >= self.max_bpm_duration_ms
        ):
            self.showing_metadata = True
            self.elapsed_time_ms = 0

        # Delegate rendering to the active screen
        if self.showing_metadata:
            self.metadata_screen.process(window, clock, peripheral_manager, orientation)
        else:
            self.max_bpm_screen.process(window, clock, peripheral_manager, orientation)
