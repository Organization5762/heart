import io
import time
from dataclasses import dataclass, field
from functools import cached_property

import pygame
from PIL import Image

from heart.device import Device
from heart.device.beats.websocket import WebSocket
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.utilities.env.parsing import _env_int

STREAMED_SCREEN_SCALE_FACTOR = 4
STREAMED_SCREEN_FRAME_FPS_ENV_VAR = "BEATS_STREAM_FRAME_FPS"
DEFAULT_STREAMED_SCREEN_FRAME_FPS = 20


@dataclass
class StreamedScreen(Device):
    _last_frame_sent_monotonic: float = field(default=0.0, init=False, repr=False)

    def individual_display_size(self) -> tuple[int, int]:
        return (64, 64)

    @cached_property
    def scale_factor(self) -> int:
        return STREAMED_SCREEN_SCALE_FACTOR

    @cached_property
    def frame_rate_limit_fps(self) -> int:
        return _env_int(
            STREAMED_SCREEN_FRAME_FPS_ENV_VAR,
            default=DEFAULT_STREAMED_SCREEN_FRAME_FPS,
            minimum=0,
        )

    def __post_init__(self) -> None:
        self.websocket = WebSocket()

    def set_screen(self, screen: pygame.Surface) -> None:
        image_bytes = pygame.image.tostring(screen, RGBA_IMAGE_FORMAT)
        image = Image.frombuffer(
            RGBA_IMAGE_FORMAT,
            screen.get_size(),
            image_bytes,
            "raw",
            RGBA_IMAGE_FORMAT,
            0,
            1,
        )
        self.set_image(image)

    def set_image(self, image: Image.Image) -> None:
        expected_sizes = {
            self.full_display_size(),
            self.scaled_display_size(),
        }
        assert image.size in expected_sizes, (
            "Image size does not match display size. "
            f"Image size: {image.size}, expected one of: {sorted(expected_sizes)}"
        )
        if not self._should_send_frame():
            return

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        frame_bytes = buf.getvalue()

        self.websocket.send(
            kind="frame",
            payload=frame_bytes,
        )

    def _should_send_frame(self) -> bool:
        fps = self.frame_rate_limit_fps
        if fps <= 0:
            return True

        now = time.monotonic()
        min_interval_seconds = 1.0 / fps
        if (
            self._last_frame_sent_monotonic
            and now - self._last_frame_sent_monotonic < min_interval_seconds
        ):
            return False

        self._last_frame_sent_monotonic = now
        return True
