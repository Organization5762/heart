import io
from dataclasses import dataclass

import pygame
from PIL import Image

from heart.device import Device
from heart.device.beats.websocket import WebSocket
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT


@dataclass
class StreamedScreen(Device):
    def individual_display_size(self) -> tuple[int, int]:
        return (64, 64)

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
        assert image.size == self.full_display_size()
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        frame_bytes = buf.getvalue()

        self.websocket.send(
            kind="frame",
            payload=frame_bytes,
        )

    
