import time
from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
from pygame import font, Surface, time
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.heart_rates import (
    current_bpms,
) 
from heart.device import Orientation

from heart.display.renderers.flame import FlameGenerator


AVATAR_MAPPINGS = {
    "sri": "0E906",  # PINK
    "clem": "0EA8E",  # Green
    "faye": "0ED2A",  # YELLOW
    "will": "09F90",  # BLACK
    "seb": "0EA01",  # RED
    # "michael": "0EA19",  # BLUE
    "cal": "0EB14",  # PURPLE
}

# Timeout for inactive sensors (30 seconds)
SENSOR_TIMEOUT_MS = 30000


class MaxBpmScreen(BaseRenderer):
    def __init__(self) -> None:
        self.device_display_mode = DeviceDisplayMode.FULL
        self.current_frame = 0

        self._flame_edges = {
            "bottom": FlameGenerator(64, 16),
            "top": FlameGenerator(64, 16),
            "left": FlameGenerator(64, 16),
            "right": FlameGenerator(64, 16),
        }

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
        self._flame = FlameGenerator(width=64, height=16)  # bottom strip 16 px tall

    def display_number(self, window, number, x, y):
        my_font = font.Font(Loader._resolve_path("Grand9K Pixel.ttf"), 8)
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        # Center the text horizontally on the screen
        text_rect = text.get_rect(
            center=(x + 32, y + 56)  # Center relative to the 64x64 screen section
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
        top_bpms = []
        if current_bpms:  # Check if the dictionary is not empty
            try:
                # Create a list of (address, bpm) tuples for non-zero BPM values
                active_bpms = [
                    (addr, bpm) for addr, bpm in current_bpms.items() if bpm > 0
                ]

                if active_bpms:
                    # Sort by BPM in descending order
                    sorted_bpms = sorted(active_bpms, key=lambda x: x[1], reverse=True)

                    # Get the top 4 BPMs (or fewer if less than 4 are available)
                    top_bpms = sorted_bpms[:4]

                    # Map device IDs to avatar names
                    for i, (addr, bpm) in enumerate(top_bpms):
                        avatar_name = "seb"  # Default
                        for name, device_id in AVATAR_MAPPINGS.items():
                            if addr == device_id:
                                avatar_name = name
                                break
                        top_bpms[i] = (addr, bpm, avatar_name)
            except ValueError:
                # Handle cases where current_bpms might be temporarily empty or contain non-numeric data
                pass

        # Fill with defaults if we have fewer than 4 active monitors
        while len(top_bpms) < 4:
            top_bpms.append(("", 0, "seb"))

        # --- Rendering ---
        # Render each of the top 4 BPMs on a different screen section
        screen_positions = [(0, 0), (64, 0), (128, 0), (192, 0)]

        for i, (addr, bpm, avatar_name) in enumerate(top_bpms[:4]):
            x, y = screen_positions[i]

            # Get the avatar image
            image = self.avatar_images.get(avatar_name, self.avatar_images["seb"])

            # Center the avatar image in the middle of the 64x64 screen section
            image_width = image.get_width()
            image_height = image.get_height()
            center_x = x + (64 - image_width) // 2
            center_y = (
                y + (64 - image_height) // 2 - 8
            )  # Keep the slight y-offset for visual balance

            # Render the avatar at the center position
            window.blit(image, (center_x, center_y))

            # Display the BPM number
            self.display_number(window, bpm, x, y)

            # Render flames for each screen section
            t = time.get_ticks() * 2 / 1000.0  # floating‑point seconds

            window.blit(
                self._flame_edges["bottom"].surface(t, "bottom"), (x, y + 64 - 16)
            )
            window.blit(self._flame_edges["top"].surface(t, "top"), (x, y))
            window.blit(self._flame_edges["left"].surface(t, "left"), (x, y))
            window.blit(self._flame_edges["right"].surface(t, "right"), (x + 48, y))

        self.time_since_last_update += clock.get_time()
