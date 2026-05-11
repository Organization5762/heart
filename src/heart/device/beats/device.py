import io
from dataclasses import dataclass, field
from functools import cached_property
from typing import Protocol

import pygame
from PIL import Image

from heart.device import Device
from heart.device.beats.websocket import WebSocket
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT

STREAMED_SCREEN_SCALE_FACTOR = 4


class FrameWebSocket(Protocol):
    def send(self, kind: str, payload: bytes) -> None: ...


@dataclass
class StreamedScreen(Device):
    websocket: FrameWebSocket | None = field(default=None, repr=False)

    def individual_display_size(self) -> tuple[int, int]:
        return (64, 64)

    @cached_property
    def scale_factor(self) -> int:
        return STREAMED_SCREEN_SCALE_FACTOR

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
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        frame_bytes = buf.getvalue()

        self._websocket().send(
            kind="frame",
            payload=frame_bytes,
        )

    def _websocket(self) -> FrameWebSocket:
        if self.websocket is None:
            self.websocket = WebSocket()
        return self.websocket
