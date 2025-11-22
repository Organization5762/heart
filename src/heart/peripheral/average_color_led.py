"""Peripheral that mirrors an LED matrix onto a single LED device."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast

from PIL import Image, ImageStat

from heart.device import Device
from heart.events.types import DisplayFrame
from heart.peripheral.core import Input, Peripheral
from heart.peripheral.led_matrix import LEDMatrixDisplay


def _rgb_mean(image: Image.Image) -> tuple[int, int, int]:
    stat = ImageStat.Stat(image.convert("RGB"))
    mean = tuple(int(round(channel)) for channel in stat.mean[:3])
    return cast(tuple[int, int, int], mean)


@dataclass(slots=True)
class _FrameHandler:
    source_display_id: int
    update_device: Callable[[tuple[int, int, int]], None]

    def __call__(self, input_event: Input) -> None:
        payload = input_event.data
        if (
            not isinstance(payload, DisplayFrame)
            or input_event.producer_id != self.source_display_id
        ):
            return
        colour = _rgb_mean(payload.to_image())
        self.update_device(colour)


class AverageColorLED(Peripheral):
    """Mirror the average matrix colour onto a single LED device."""

    def __init__(
        self,
        *,
        device: Device,
        source_display: LEDMatrixDisplay,
    ) -> None:
        super().__init__()
        self._device = device
        self._frame_handler = _FrameHandler(
            source_display_id=source_display.producer_id,
            update_device=self._update_device,
        )

    def _update_device(self, colour: tuple[int, int, int]) -> None:
        image = Image.new("RGB", self._device.full_display_size(), colour)
        self._device.set_image(image)

    def run(self) -> None:  # pragma: no cover - passive peripheral
        return None

