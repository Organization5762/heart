from __future__ import annotations

import pygame
from pygame import Surface, font, time
from reactivex.disposable import Disposable

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.navigation import ComposedRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import AtomicBaseRenderer
from heart.renderers.flame import FlameRenderer
from heart.renderers.max_bpm_screen.provider import (AVATAR_MAPPINGS,
                                                     AvatarBpmStateProvider)
from heart.renderers.max_bpm_screen.state import AvatarBpmRendererState


class MaxBpmScreen(ComposedRenderer):
    def __init__(self) -> None:
        flame_renderer = FlameRenderer()
        avatar_renderer = AvatarBpmRenderer()

        super().__init__([flame_renderer, avatar_renderer])
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.is_flame_renderer = True


class AvatarBpmRenderer(AtomicBaseRenderer[AvatarBpmRendererState]):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self._subscription: Disposable | None = None

        self.avatar_images = {}
        for name in AVATAR_MAPPINGS.keys():
            try:
                self.avatar_images[name] = Loader.load(f"avatars/{name}_32.png")
            except Exception:
                print(f"Could not load avatar for {name}")

        self.image = self.avatar_images.get("seb")

    def display_number(self, window: Surface, number: int, x: int, y: int) -> None:
        my_font = font.Font(Loader._resolve_path("Grand9K Pixel.ttf"), 8)
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(x, y + 40))
        window.blit(text, text_rect)

    def real_process(
        self,
        window: Surface,
        clock: time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state
        if state.bpm is None:
            window.fill((0, 0, 0))
            return

        window_width = window.get_width()
        window_height = window.get_height()

        image = self.avatar_images.get(state.avatar_name, self.image)
        center_x = (window_width - image.get_width()) // 2
        center_y = (window_height - image.get_height()) // 2 - 8
        window.blit(image, (center_x, center_y))

        self.display_number(window, state.bpm, window_width // 2, center_y)

    def reset(self) -> None:
        if self._subscription is not None:
            self._subscription.dispose()
            self._subscription = None
        super().reset()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> AvatarBpmRendererState:
        provider = AvatarBpmStateProvider(peripheral_manager)

        initial_state = AvatarBpmRendererState.initial()
        self.set_state(initial_state)
        self._subscription = provider.observable().subscribe(on_next=self.set_state)

        return initial_state
