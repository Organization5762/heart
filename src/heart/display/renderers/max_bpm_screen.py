import time

from pygame import Surface, font, time

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.display.renderers.flame import FlameGenerator, FlameRenderer
from heart.navigation import ComposedRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.heart_rates import (
    current_bpms,
)

# Number of top BPMs to display (1-4)
MAX_DISPLAYED_BPMS = 1

AVATAR_MAPPINGS = {
    "sri": "0E906",  # PINK
    "clem": "0EA8E",  # Green
    "faye": "0ED2A",  # YELLOW
    "will": "09F90",  # BLACK
    "seb": "0EA01",  # RED
    "lampe": "0EA19",  # BLUE
    "cal": "0EB14",  # PURPLE
    "ditto": "08E5F",  # WHITE
}

# Timeout for inactive sensors (30 seconds)
SENSOR_TIMEOUT_MS = 30000


class MaxBpmScreen(ComposedRenderer):
    def __init__(self) -> None:
        # Create the flame renderer
        flame_renderer = FlameRenderer()

        # Create the avatar renderer
        avatar_renderer = AvatarBpmRenderer()

        # Initialize the composed renderer with both components
        super().__init__([flame_renderer, avatar_renderer])
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.is_flame_renderer = True


class AvatarBpmRenderer(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.current_frame = 0

        # Load avatar images for all users
        self.avatar_images = {}
        for name, sensor_id in AVATAR_MAPPINGS.items():
            try:
                self.avatar_images[name] = Loader.load(f"avatars/{name}_32.png")
            except:
                print(f"Could not load avatar for {name}")

        # Default avatar
        self.image = self.avatar_images["seb"]

        self.time_since_last_update = 0
        self.time_between_frames_ms = 400

    def display_number(self, window, number, x, y):
        my_font = font.Font(Loader._resolve_path("Grand9K Pixel.ttf"), 8)
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        # Center the text horizontally on the screen
        text_rect = text.get_rect(
            center=(x, y + 40)  # Center relative to the avatar position
        )
        window.blit(text, text_rect)

    def process(
        self,
        window: Surface,
        clock: time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # --- BPM Calculation ---
        top_bpm = None
        if current_bpms:  # Check if the dictionary is not empty
            try:
                # Create a list of (address, bpm) tuples for non-zero BPM values
                active_bpms = [
                    (addr, bpm) for addr, bpm in current_bpms.items() if bpm > 0
                ]

                if active_bpms:
                    # Sort by BPM in descending order and get the highest
                    sorted_bpms = sorted(active_bpms, key=lambda x: x[1], reverse=True)
                    highest_bpm = sorted_bpms[0]

                    # Map device ID to avatar name
                    avatar_name = "faye"  # Default
                    for name, device_id in AVATAR_MAPPINGS.items():
                        if highest_bpm[0] == device_id:
                            avatar_name = name
                            break

                    top_bpm = (highest_bpm[0], highest_bpm[1], avatar_name)
            except ValueError:
                # Handle cases where current_bpms might be temporarily empty or contain non-numeric data
                pass

        # Draw the highest BPM in the center of the screen
        if top_bpm:
            addr, bpm, avatar_name = top_bpm

            # Get window dimensions
            window_width = window.get_width()
            window_height = window.get_height()

            # Avatar --------------------------------------------------------------------
            image = self.avatar_images.get(avatar_name, self.avatar_images["seb"])
            center_x = (window_width - image.get_width()) // 2
            center_y = (
                window_height - image.get_height()
            ) // 2 - 8  # retain visual offset
            window.blit(image, (center_x, center_y))

            # BPM number ----------------------------------------------------------------
            self.display_number(window, bpm, window_width // 2, center_y)
