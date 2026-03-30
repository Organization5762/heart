from __future__ import annotations

import reactivex

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.navigation import ComposedRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.combined_bpm_screen.provider import (
    DEFAULT_MAX_BPM_DURATION_MS, DEFAULT_METADATA_DURATION_MS,
    CombinedBpmScreenStateProvider)
from heart.renderers.combined_bpm_screen.state import CombinedBpmScreenState
from heart.renderers.flame.renderer import FlameRenderer
from heart.renderers.max_bpm_screen import AvatarBpmRenderer
from heart.renderers.metadata_screen import MetadataScreen
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.surface.provider import RendererSurfaceProvider


class CombinedBpmScreen(StatefulBaseRenderer[CombinedBpmScreenState]):
    def __init__(
        self,
        metadata_duration_ms: int = DEFAULT_METADATA_DURATION_MS,
        max_bpm_duration_ms: int = DEFAULT_MAX_BPM_DURATION_MS,
        provider: CombinedBpmScreenStateProvider | None = None,
    ) -> None:
        self.metadata_screen = MetadataScreen()
        self.max_bpm_screen: ComposedRenderer | None = None

        self.metadata_duration_ms = metadata_duration_ms
        self.max_bpm_duration_ms = max_bpm_duration_ms

        self._provider = provider or CombinedBpmScreenStateProvider(
            metadata_duration_ms=metadata_duration_ms,
            max_bpm_duration_ms=max_bpm_duration_ms,
        )
        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.FULL

        self._peripheral_manager: PeripheralManager | None = None

    def _build_max_bpm_screen(
        self, window: DisplayContext
    ) -> ComposedRenderer:
        max_bpm_screen = ComposedRenderer(
            renderers=[],
            surface_provider=RendererSurfaceProvider(display_context=window),
        )
        max_bpm_screen.add_renderer(FlameRenderer())
        max_bpm_screen.add_renderer(AvatarBpmRenderer())
        return max_bpm_screen

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self.metadata_screen.initialize(
            window=window,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        self.max_bpm_screen = self._build_max_bpm_screen(window)
        self.max_bpm_screen.initialize(
            window=window,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        super().initialize(window, peripheral_manager, orientation)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[CombinedBpmScreenState]:
        return self._provider.observable(peripheral_manager)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if self.max_bpm_screen is None:
            raise RuntimeError("CombinedBpmScreen must be initialized before processing")
        peripheral_manager = self._peripheral_manager
        if self.state.showing_metadata:
            self.metadata_screen._internal_process(
                window=window,
                peripheral_manager=peripheral_manager,
                orientation=orientation,
            )
        else:
            self.max_bpm_screen._internal_process(
                window=window,
                peripheral_manager=peripheral_manager,
                orientation=orientation,
            )

    def reset(self) -> None:
        self.metadata_screen.reset()
        if self.max_bpm_screen is not None:
            self.max_bpm_screen.reset()
            self.max_bpm_screen = None

        self._peripheral_manager = None
        super().reset()
