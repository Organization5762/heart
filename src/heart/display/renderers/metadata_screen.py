from pygame import Rect, Surface, draw, time

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.display.renderers.max_bpm_screen import AVATAR_MAPPINGS
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.heart_rates import battery_status, current_bpms
from heart.utilities.logging import get_logger

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400

logger = get_logger("HeartRateManager")


class MetadataScreen(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.current_frame = 0

        # Define colors for different heart rate monitors
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
        self.heart_images = {}
        for color in self.colors:
            self.heart_images[color] = {
                "small": Loader.load(f"hearts/{color}/small.png"),
                "med": Loader.load(f"hearts/{color}/med.png"),
                "big": Loader.load(f"hearts/{color}/big.png"),
            }

        # Load avatar images
        self.avatar_images = {}
        for name, sensor_id in AVATAR_MAPPINGS.items():
            try:
                self.avatar_images[sensor_id] = Loader.load(f"avatars/{name}_16.png")
            except Exception:
                logger.warning(f"Could not load avatar for {name}")

        self.time_since_last_update = 0
        self.time_between_frames_ms = DEFAULT_TIME_BETWEEN_FRAMES_MS

        # Track animation state for each heart rate monitor
        self.heart_states = {}  # {id: {"up": bool, "color_index": int, "last_update": time}}

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

    def process(
        self,
        window: Surface,
        clock: time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # Get all active heart rate monitors
        active_monitors = list(current_bpms.keys())

        # Initialize or update heart states for each monitor
        for i, monitor_id in enumerate(active_monitors):
            if monitor_id not in self.heart_states:
                self.heart_states[monitor_id] = {
                    "up": True,
                    "color_index": i % len(self.colors),
                    "last_update": 0,
                }

        # Remove heart states for monitors that are no longer active
        for monitor_id in list(self.heart_states.keys()):
            if monitor_id not in active_monitors:
                del self.heart_states[monitor_id]

        # Calculate positions for each heart rate display
        # Each metadata is 32x32, screen is 64x256
        # We can fit 2 across and 8 down
        max_per_col = 2
        max_cols = 8

        for i, monitor_id in enumerate(
            active_monitors[: max_per_col * max_cols]
        ):  # Limit to what fits on screen
            col = i // max_per_col
            row = i % max_per_col

            x = col * 32
            y = row * 32

            # Get current BPM and update animation timing
            current_bpm = current_bpms.get(
                monitor_id, 60
            )  # Default to 60 BPM if not found

            if current_bpm > 0:
                # Convert BPM to milliseconds between beats (60000ms / BPM)
                time_between_beats = (
                    60000 / current_bpm / 2
                )  # Divide by 2 for heart animation (up/down)
            else:
                time_between_beats = DEFAULT_TIME_BETWEEN_FRAMES_MS

            # Update animation state
            state = self.heart_states[monitor_id]
            state["last_update"] += clock.get_time()

            if state["last_update"] > time_between_beats:
                state["last_update"] = 0
                state["up"] = not state["up"]

            # Check if we have an avatar for this monitor_id
            use_avatar = monitor_id in self.avatar_images

            # Determine which image to use
            if use_avatar:
                image = self.avatar_images[monitor_id]
            else:
                color = self.colors[state["color_index"]]
                image_key = "small" if state["up"] else "med"
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
                self.display_number(
                    window, current_bpms.get(monitor_id, 0), pos_x, pos_y
                )
                self.display_battery_status(window, monitor_id, pos_x, pos_y)

            self.time_since_last_update += clock.get_time()
