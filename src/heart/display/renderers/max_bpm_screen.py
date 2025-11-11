from dataclasses import dataclass

from pygame import Surface, font, time

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.flame import FlameRenderer
from heart.navigation import ComposedRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.heart_rates import current_bpms

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


@dataclass
class AvatarBpmRendererState:
    sensor_id: str | None = None
    bpm: int | None = None
    avatar_name: str | None = None


class AvatarBpmRenderer(AtomicBaseRenderer[AvatarBpmRendererState]):
    def __init__(self) -> None:
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.MIRRORED

        # Load avatar images for all users
        self.avatar_images = {}
        for name, sensor_id in AVATAR_MAPPINGS.items():
            try:
                self.avatar_images[name] = Loader.load(f"avatars/{name}_32.png")
            except Exception:
                print(f"Could not load avatar for {name}")

        # Default avatar
        self.image = self.avatar_images["seb"]

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
        top_bpm = self._select_top_bpm()
        if top_bpm is None:
            if (
                self.state.sensor_id is not None
                or self.state.bpm is not None
                or self.state.avatar_name is not None
            ):
                self.update_state(sensor_id=None, bpm=None, avatar_name=None)
            window.fill((0, 0, 0))
            return

        sensor_id, bpm, avatar_name = top_bpm
        state = self.state
        if (
            sensor_id != state.sensor_id
            or bpm != state.bpm
            or avatar_name != state.avatar_name
        ):
            self.update_state(sensor_id=sensor_id, bpm=bpm, avatar_name=avatar_name)

        # Draw the highest BPM in the center of the screen
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

    def _select_top_bpm(self) -> tuple[str, int, str] | None:
        if not current_bpms:
            return None

        try:
            active_bpms = [
                (addr, bpm) for addr, bpm in current_bpms.items() if bpm > 0
            ]
        except ValueError:
            return None

        if not active_bpms:
            return None

        sorted_bpms = sorted(active_bpms, key=lambda x: x[1], reverse=True)
        highest_bpm = sorted_bpms[0]

        avatar_name = "faye"
        for name, device_id in AVATAR_MAPPINGS.items():
            if highest_bpm[0] == device_id:
                avatar_name = name
                break

        return highest_bpm[0], highest_bpm[1], avatar_name

    def _create_initial_state(self) -> AvatarBpmRendererState:
        return AvatarBpmRendererState()
