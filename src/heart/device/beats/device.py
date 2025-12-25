import io
from dataclasses import dataclass

from PIL import Image

from heart.device import Device
from heart.device.beats.websocket import WebSocket


@dataclass
class StreamedScreen(Device):
    def individual_display_size(self) -> tuple[int, int]:
        return (64, 64)

    def __post_init__(self) -> None:
        self.websocket = WebSocket()

    def set_image(self, image: Image.Image) -> None:
        assert image.size == self.full_display_size()
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        frame_bytes = buf.getvalue()

        self.websocket.send(
            kind="frame",
            payload=frame_bytes,
        )
