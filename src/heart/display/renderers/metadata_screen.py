from dataclasses import dataclass, field, replace
from typing import Dict

import pygame
from pygame import Rect, Surface, draw, time

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.max_bpm_screen import AVATAR_MAPPINGS
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.heart_rates import battery_status, current_bpms
from heart.utilities.logging import get_logger

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400

logger = get_logger("HeartRateManager")


@dataclass(frozen=True)
class HeartAnimationState:
    up: bool
    color_index: int
    last_update_ms: float


@dataclass(frozen=True)
class MetadataScreenState:
    heart_states: Dict[str, HeartAnimationState] = field(default_factory=dict)
    time_since_last_update_ms: float = 0.0


class MetadataScreen(AtomicBaseRenderer[MetadataScreenState]):
    def __init__(self) -> None:
        self.colors = [
            "bluer",
            "blue",
            "green",
            "orange",
            "pink",
            "purple",
            "teal",
            "yellow",
        ]

        # Load heart images for each color
        self.heart_images: Dict[str, dict[str, Surface]] = {}
        for color in self.colors:
            self.heart_images[color] = {
                "small": Loader.load(f"hearts/{color}/small.png"),
                "med": Loader.load(f"hearts/{color}/med.png"),
                "big": Loader.load(f"hearts/{color}/big.png"),
            }

        # Load avatar images
        self.avatar_images: Dict[str, Surface] = {}
        for name, sensor_id in AVATAR_MAPPINGS.items():
            try:
                self.avatar_images[sensor_id] = Loader.load(f"avatars/{name}_16.png")
            except Exception:
                logger.warning(f"Could not load avatar for {name}")

        self.time_between_frames_ms = DEFAULT_TIME_BETWEEN_FRAMES_MS

        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

    def display_number(self, window, number, x, y):
        my_font = Loader.load_font("Grand9K Pixel.ttf")
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(x + 16, y + 25))
        window.blit(text, text_rect)

    def display_battery_status(self, window, monitor_id, x, y):
        # Get battery status if available
        battery_level = battery_status.get(monitor_id, None)

        if battery_level is not None:
            # Determine battery status color
            if battery_level < 10:
                color = (255, 0, 0)  # Red for critical
            elif battery_level < 25:
                color = (255, 165, 0)  # Orange for low
            else:
                color = (0, 255, 0)  # Green for ok

            # Draw a 2x2 rectangle
            rect_size = 2
            draw.rect(
                window,
                color,
                Rect(
                    x + 30 - rect_size, y + 30 - rect_size, rect_size * 2, rect_size * 2
                ),
            )

    def real_process(
        self,
        window: Surface,
        clock: time.Clock,
        orientation: Orientation,
    ) -> None:
        # Get all active heart rate monitors
        active_monitors = list(current_bpms.keys())

        elapsed_ms = float(clock.get_time())
        self._synchronise_heart_states(active_monitors, elapsed_ms)
        state = self.state
        heart_states = state.heart_states

        # Calculate positions for each heart rate display
        # Each metadata is 32x32, screen is 64x256
        # We can fit 2 across and 8 down
        max_per_col = 2
        max_cols = 8
        max_visible = max_per_col * max_cols

        for i, monitor_id in enumerate(
            active_monitors[:max_visible]
        ):  # Limit to what fits on screen
            col = i // max_per_col
            row = i % max_per_col

            x = col * 32
            y = row * 32

            heart_state = heart_states.get(monitor_id)
            if heart_state is None:
                continue

            # Get current BPM and update animation timing
            current_bpm = current_bpms.get(monitor_id, 0)

            # Check if we have an avatar for this monitor_id
            use_avatar = monitor_id in self.avatar_images

            # Determine which image to use
            if use_avatar:
                image = self.avatar_images[monitor_id]
            else:
                color = self.colors[heart_state.color_index]
                image_key = "small" if heart_state.up else "med"
                image = self.heart_images[color][image_key]

            # Calculate how many times to repeat based on number of active monitors
            repeat_positions = [(x, y)]

            if len(active_monitors) <= 8:
                repeat_positions.append((x + 128, y))

            if len(active_monitors) <= 4:
                repeat_positions.append((x + 64, y))
                repeat_positions.append((x + 192, y))

            # Draw the image and metadata at each position
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
        orientation: Orientation
    ):
        return MetadataScreenState()

    def _synchronise_heart_states(
        self, active_monitors: list[str], elapsed_ms: float
    ) -> None:
        max_visible = 16

        def mutator(state: MetadataScreenState) -> MetadataScreenState:
            heart_states = dict(state.heart_states)

            for i, monitor_id in enumerate(active_monitors):
                if monitor_id not in heart_states:
                    heart_states[monitor_id] = HeartAnimationState(
                        up=True,
                        color_index=i % len(self.colors),
                        last_update_ms=0.0,
                    )

            for monitor_id in list(heart_states.keys()):
                if monitor_id not in active_monitors:
                    del heart_states[monitor_id]

            for monitor_id in active_monitors[:max_visible]:
                animation = heart_states.get(monitor_id)
                if animation is None:
                    continue

                current_bpm = current_bpms.get(monitor_id, 60)
                if current_bpm > 0:
                    time_between_beats = 60000 / current_bpm / 2
                else:
                    time_between_beats = DEFAULT_TIME_BETWEEN_FRAMES_MS

                accumulated = animation.last_update_ms + elapsed_ms
                if accumulated > time_between_beats:
                    accumulated = 0.0
                    up = not animation.up
                else:
                    up = animation.up

                heart_states[monitor_id] = replace(
                    animation, up=up, last_update_ms=accumulated
                )

            return MetadataScreenState(
                heart_states=heart_states,
                time_since_last_update_ms=
                    state.time_since_last_update_ms + elapsed_ms,
            )

        self.mutate_state(mutator)
