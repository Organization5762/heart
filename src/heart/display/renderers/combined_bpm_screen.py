from dataclasses import dataclass

import pygame
from pygame import Surface
from pygame import time as pygame_time

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.max_bpm_screen import MaxBpmScreen
from heart.display.renderers.metadata_screen import MetadataScreen
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class CombinedBpmScreenState:
    peripheral_manager: PeripheralManager
    elapsed_time_ms: int = 0
    showing_metadata: bool = True


class CombinedBpmScreen(AtomicBaseRenderer[CombinedBpmScreenState]):
    def __init__(self) -> None:
        # Create both renderers
        self.metadata_screen = MetadataScreen()
        self.max_bpm_screen = MaxBpmScreen()

        # Screen swap timing
        self.metadata_duration_ms = 12000  # 12 seconds
        self.max_bpm_duration_ms = 5000  # 5 seconds

        self.is_flame_renderer = True

        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> CombinedBpmScreenState:
        self.metadata_screen.initialize(window, clock, peripheral_manager, orientation)
        self.max_bpm_screen.initialize(window, clock, peripheral_manager, orientation)
        return CombinedBpmScreenState(
            peripheral_manager=peripheral_manager
        )

    def real_process(
        self,
        window: Surface,
        clock: pygame_time.Clock,
        orientation: Orientation,
    ) -> None:
        elapsed_time = self.state.elapsed_time_ms + clock.get_time()
        showing_metadata = self.state.showing_metadata

        if showing_metadata and elapsed_time >= self.metadata_duration_ms:
            showing_metadata = False
            elapsed_time = 0
        elif not showing_metadata and elapsed_time >= self.max_bpm_duration_ms:
            showing_metadata = True
            elapsed_time = 0

        # TODO: Emit an event that will also be consumable as state here
        self.update_state(
            elapsed_time_ms=elapsed_time,
            showing_metadata=showing_metadata,
        )

        if showing_metadata:
            self.metadata_screen.process(window, clock, peripheral_manager=self.state.peripheral_manager, orientation=orientation)
        else:
            self.max_bpm_screen.process(window, clock, peripheral_manager=self.state.peripheral_manager, orientation=orientation)

    def reset(self) -> None:
        self.metadata_screen.reset()
        self.max_bpm_screen.reset()
        super().reset()
