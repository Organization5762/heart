from __future__ import annotations

import numpy as np
from PIL import Image

from heart.peripheral.led_matrix import LEDMatrixDisplay


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
