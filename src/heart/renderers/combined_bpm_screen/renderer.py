from __future__ import annotations

import pygame
from pygame import Surface
from pygame import time as pygame_time
from reactivex.disposable import Disposable

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.combined_bpm_screen.provider import (
    DEFAULT_MAX_BPM_DURATION_MS, DEFAULT_METADATA_DURATION_MS,
    CombinedBpmScreenStateProvider)
from heart.renderers.combined_bpm_screen.state import CombinedBpmScreenState
from heart.renderers.max_bpm_screen import MaxBpmScreen
from heart.renderers.metadata_screen import MetadataScreen


class CombinedBpmScreen(StatefulBaseRenderer[CombinedBpmScreenState]):
    def __init__(
        self,
        metadata_duration_ms: int = DEFAULT_METADATA_DURATION_MS,
        max_bpm_duration_ms: int = DEFAULT_MAX_BPM_DURATION_MS,
    ) -> None:
        self.metadata_screen = MetadataScreen()
        self.max_bpm_screen = MaxBpmScreen()

        self.metadata_duration_ms = metadata_duration_ms
        self.max_bpm_duration_ms = max_bpm_duration_ms

        self.is_flame_renderer = True

        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

        self._provider: CombinedBpmScreenStateProvider | None = None
        self._subscription: Disposable | None = None
        self._peripheral_manager: PeripheralManager | None = None

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> CombinedBpmScreenState:
        self._peripheral_manager = peripheral_manager
        self.metadata_screen.initialize(
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        self.max_bpm_screen.initialize(
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )

        self._provider = CombinedBpmScreenStateProvider(
            peripheral_manager=peripheral_manager,
            metadata_duration_ms=self.metadata_duration_ms,
            max_bpm_duration_ms=self.max_bpm_duration_ms,
        )

        initial_state = CombinedBpmScreenState.initial()
        self.set_state(initial_state)

        self._subscription = self._provider.observable().subscribe(on_next=self.set_state)

        return initial_state

    def real_process(
        self,
        window: Surface,
        clock: pygame_time.Clock,
        orientation: Orientation,
    ) -> None:
        peripheral_manager = self._peripheral_manager
        if self.state.showing_metadata:
            self.metadata_screen.process(
                window,
                clock,
                peripheral_manager=peripheral_manager,
                orientation=orientation,
            )
        else:
            self.max_bpm_screen.process(
                window,
                clock,
                peripheral_manager=peripheral_manager,
                orientation=orientation,
            )

    def reset(self) -> None:
        if self._subscription is not None:
            self._subscription.dispose()
            self._subscription = None

        self.metadata_screen.reset()
        self.max_bpm_screen.reset()

        self._provider = None
        self._peripheral_manager = None
        super().reset()
