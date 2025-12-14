from __future__ import annotations

from typing import Dict, Iterable

import pygame
from pygame import Rect, Surface, draw, time
from reactivex.disposable import Disposable

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.heart_rates import battery_status, current_bpms
from heart.renderers import AtomicBaseRenderer
from heart.renderers.metadata_screen.provider import \
    MetadataScreenStateProvider
from heart.renderers.metadata_screen.state import (DEFAULT_HEART_COLORS,
                                                   MetadataScreenState)
from heart.utilities.logging import get_logger

logger = get_logger("HeartRateManager")


class MetadataScreen(AtomicBaseRenderer[MetadataScreenState]):
    def __init__(self, colors: Iterable[str] | None = None) -> None:
        self.colors = list(colors) if colors is not None else list(DEFAULT_HEART_COLORS)

        self.heart_images: Dict[str, dict[str, Surface]] = {}
        for color in self.colors:
            self.heart_images[color] = {
                "small": Loader.load(f"hearts/{color}/small.png"),
                "med": Loader.load(f"hearts/{color}/med.png"),
                "big": Loader.load(f"hearts/{color}/big.png"),
            }

        self.avatar_images: Dict[str, Surface] = {}

        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

        self._provider: MetadataScreenStateProvider | None = None
        self._subscription: Disposable | None = None

    def display_number(self, window: Surface, number: int, x: int, y: int) -> None:
        my_font = Loader.load_font("Grand9K Pixel.ttf")
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(x + 16, y + 25))
        window.blit(text, text_rect)

    def display_battery_status(self, window: Surface, monitor_id: str, x: int, y: int) -> None:
        battery_level = battery_status.get(monitor_id, None)

        if battery_level is not None:
            if battery_level < 10:
                color = (255, 0, 0)
            elif battery_level < 25:
                color = (255, 165, 0)
            else:
                color = (0, 255, 0)

            rect_size = 2
            draw.rect(
                window,
                color,
                Rect(x + 30 - rect_size, y + 30 - rect_size, rect_size * 2, rect_size * 2),
            )

    def real_process(
        self,
        window: Surface,
        clock: time.Clock,
        orientation: Orientation,
    ) -> None:
        active_monitors = list(current_bpms.keys())
        state = self.state
        heart_states = state.heart_states

        max_per_col = 2
        max_cols = 8
        max_visible = max_per_col * max_cols

        for i, monitor_id in enumerate(active_monitors[:max_visible]):
            col = i // max_per_col
            row = i % max_per_col

            x = col * 32
            y = row * 32

            heart_state = heart_states.get(monitor_id)
            if heart_state is None:
                continue

            current_bpm = current_bpms.get(monitor_id, 0)

            use_avatar = monitor_id in self.avatar_images

            if use_avatar:
                image = self.avatar_images[monitor_id]
            else:
                color = self.colors[heart_state.color_index]
                image_key = "small" if heart_state.up else "med"
                image = self.heart_images[color][image_key]

            repeat_positions = [(x, y)]

            if len(active_monitors) <= 8:
                repeat_positions.append((x + 128, y))

            if len(active_monitors) <= 4:
                repeat_positions.append((x + 64, y))
                repeat_positions.append((x + 192, y))

            for pos_x, pos_y in repeat_positions:
                if use_avatar:
                    window.blit(image, (pos_x + 8, pos_y + 4))
                else:
                    window.blit(image, (pos_x, pos_y - 8))
                self.display_number(window, current_bpm, pos_x, pos_y)
                self.display_battery_status(window, monitor_id, pos_x, pos_y)

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> MetadataScreenState:
        from heart.renderers.max_bpm_screen.provider import AVATAR_MAPPINGS

        for name, sensor_id in AVATAR_MAPPINGS.items():
            try:
                self.avatar_images[sensor_id] = Loader.load(f"avatars/{name}_16.png")
            except Exception:
                logger.warning(f"Could not load avatar for {name}")

        self._provider = MetadataScreenStateProvider(
            peripheral_manager=peripheral_manager, colors=self.colors
        )

        initial_state = MetadataScreenState.initial()
        self.set_state(initial_state)

        self._subscription = self._provider.observable().subscribe(on_next=self.set_state)

        return initial_state

    def reset(self) -> None:
        if self._subscription is not None:
            self._subscription.dispose()
            self._subscription = None

        self._provider = None
        super().reset()
