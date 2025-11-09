"""Simple in-memory device modelling a single 1x1 LED pixel."""

from __future__ import annotations

from typing import cast

from PIL import Image

from heart.device import Device, Orientation, Rectangle


class SingleLEDDevice(Device):
    """Device implementation that records the colour of a single LED."""

    def __init__(self, orientation: Orientation | None = None) -> None:
        super().__init__(
            orientation=orientation or Rectangle.with_layout(columns=1, rows=1)
        )
        self._last_image: Image.Image | None = None

    def individual_display_size(self) -> tuple[int, int]:
        return (1, 1)

    def set_image(self, image: Image.Image) -> None:
        if image.size != self.full_display_size():
            raise ValueError(
                "SingleLEDDevice expects a 1x1 image; "
                f"received {image.size!r}"
            )
        if image.mode != "RGB":
            image = image.convert("RGB")
        self._last_image = image.copy()

    @property
    def last_image(self) -> Image.Image | None:
        """Return the most recently rendered image, if any."""

        return self._last_image.copy() if self._last_image is not None else None

    @property
    def last_color(self) -> tuple[int, int, int] | None:
        """Return the most recently rendered colour as an RGB tuple."""

        if self._last_image is None:
            return None
        pixel = cast(tuple[int, int, int], self._last_image.getpixel((0, 0)))
        return (int(pixel[0]), int(pixel[1]), int(pixel[2]))

