"""Validate Beats streamed device sizing so websocket frames can carry scaled atlases."""

from __future__ import annotations

from PIL import Image

from heart.device import Cube
from heart.device.beats.device import StreamedScreen


class _WebSocketStub:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    def send(self, kind: str, payload: bytes) -> None:
        self.sent.append((kind, payload))


class TestStreamedScreen:
    """Ensure the Beats streamed device accepts scaled frames so renderer output can match local preview fidelity."""

    def test_scaled_display_size_uses_fixed_scale_factor(self) -> None:
        """Verify streamed screens expose a larger render surface so Heart can render at local-preview scale before Beats downsizes it."""
        device = StreamedScreen(orientation=Cube.sides())
        device.websocket = _WebSocketStub()

        assert device.full_display_size() == (256, 64)
        assert device.scaled_display_size() == (1024, 256)

    def test_set_image_accepts_scaled_frame_size(self) -> None:
        """Verify the streamed device accepts scaled atlas images so websocket transport can carry higher-resolution totem frames."""
        device = StreamedScreen(orientation=Cube.sides())
        websocket = _WebSocketStub()
        device.websocket = websocket

        image = Image.new("RGBA", device.scaled_display_size(), color=(0, 0, 0, 255))
        device.set_image(image)

        assert len(websocket.sent) == 1
        assert websocket.sent[0][0] == "frame"
