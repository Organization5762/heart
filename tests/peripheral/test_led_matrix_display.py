from __future__ import annotations

import numpy as np
from PIL import Image

from heart.peripheral.led_matrix import LEDMatrixDisplay
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

def _solid_image(width: int, height: int, *, value: int) -> Image.Image:
    array = np.full((height, width, 3), value, dtype=np.uint8)
    return Image.fromarray(array, mode="RGB")


class TestPeripheralLedMatrixDisplay:
    """Group Peripheral Led Matrix Display tests so peripheral led matrix display behaviour stays reliable. This preserves confidence in peripheral led matrix display for end-to-end scenarios."""

    def test_publish_image_validates_dimensions(self) -> None:
        """Verify that publish image validates dimensions. This keeps the system behaviour reliable for operators."""
        peripheral = LEDMatrixDisplay(width=2, height=2)
        image = _solid_image(3, 2, value=10)

        try:
            peripheral.publish_image(image)
        except ValueError as exc:
            assert "dimensions" in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("ValueError expected when dimensions do not match")

    def test_publish_image_emits_latest_frame(self) -> None:
        """Verify that publish image emits frames to observers so downstream monitors can track LED output health."""
        peripheral = LEDMatrixDisplay(width=2, height=2)
        image = _solid_image(2, 2, value=7)
        received: list = []

        subscription = peripheral.observe.subscribe(
            on_next=lambda envelope: received.append(envelope.data),
        )
        frame = peripheral.publish_image(image)
        subscription.dispose()

        assert received == [frame]
