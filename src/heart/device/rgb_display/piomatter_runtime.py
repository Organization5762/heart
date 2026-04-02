"""Piomatter-backed simple RGB display runtime.

This is the practical bring-up path for Pi 5 while the clean-room raw PIO
transport is still converging. It keeps Heart on a known-good Piomatter signal
path, but preserves the same `submit_rgba()` / canvas-shaped API that the rest
of the Python display stack already expects.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import Final, cast

import numpy as np
from PIL import Image

from heart.device import Orientation
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_PIOMATTER_PINOUT: Final[str] = "adafruit-matrix-bonnet"
DEFAULT_N_PLANES: Final[int] = 10
DEFAULT_N_TEMPORAL_PLANES: Final[int] = 2
PINOUT_ATTRIBUTE_NAMES: Final[dict[str, str]] = {
    "adafruit-matrix-bonnet": "AdafruitMatrixBonnet",
    "adafruit-matrix-bonnet-bgr": "AdafruitMatrixBonnetBGR",
    "adafruit-matrix-hat": "AdafruitMatrixHat",
    "adafruit-matrix-hat-bgr": "AdafruitMatrixHatBGR",
}


def build_piomatter_matrix_driver(
    piomatter_module: ModuleType,
    orientation: Orientation,
    pinout_name: str = DEFAULT_PIOMATTER_PINOUT,
) -> "PiomatterMatrixDriver":
    """Build a Piomatter-backed matrix driver for the configured Heart geometry."""

    panel_rows = Configuration.panel_rows()
    panel_cols = Configuration.panel_columns()
    width = panel_cols * orientation.layout.columns
    height = panel_rows * orientation.layout.rows
    n_addr_lines = infer_addr_lines(height)
    pinout_attr = PINOUT_ATTRIBUTE_NAMES.get(pinout_name)
    if pinout_attr is None:
        supported = ", ".join(sorted(PINOUT_ATTRIBUTE_NAMES))
        raise ValueError(
            "Piomatter backend only supports pinouts "
            f"{supported}; received {pinout_name!r}."
        )
    geometry = piomatter_module.Geometry(
        width=width,
        height=height,
        n_addr_lines=n_addr_lines,
        rotation=piomatter_module.Orientation.Normal,
        n_planes=DEFAULT_N_PLANES,
        n_temporal_planes=DEFAULT_N_TEMPORAL_PLANES,
    )
    framebuffer = np.zeros((geometry.height, geometry.width, 3), dtype=np.uint8)
    matrix = piomatter_module.PioMatter(
        colorspace=piomatter_module.Colorspace.RGB888Packed,
        pinout=getattr(piomatter_module.Pinout, pinout_attr),
        framebuffer=framebuffer,
        geometry=geometry,
    )
    return PiomatterMatrixDriver(
        framebuffer=framebuffer,
        height=geometry.height,
        matrix=matrix,
        width=geometry.width,
    )


def infer_addr_lines(height: int) -> int:
    """Infer HUB75 address lines from the logical matrix height."""

    if height <= 0 or height % 2 != 0:
        raise ValueError(
            f"Piomatter backend requires a positive even display height; received {height}."
        )
    return max(1, (height // 2).bit_length() - 1)


@dataclass
class PiomatterFrameCanvas:
    """Offscreen RGBA canvas that matches the minimal rgbmatrix worker API."""

    width: int
    height: int
    image: Image.Image

    @classmethod
    def create(cls, width: int, height: int) -> "PiomatterFrameCanvas":
        """Create a blank RGBA canvas."""

        return cls(width=width, height=height, image=Image.new("RGBA", (width, height)))

    def Clear(self) -> None:
        """Reset the offscreen canvas to transparent black."""

        self.image.paste((0, 0, 0, 0), (0, 0, self.width, self.height))

    def SetImage(self, image: Image.Image, x: int, y: int) -> None:
        """Paste a Pillow image onto the offscreen canvas."""

        self.image.paste(image.convert("RGBA"), (x, y))


class PiomatterMatrixDriver:
    """Small adapter that presents Piomatter through Heart's matrix protocol."""

    def __init__(
        self,
        matrix: object,
        framebuffer: np.ndarray,
        width: int,
        height: int,
    ) -> None:
        self._matrix = matrix
        self._framebuffer = framebuffer
        self._width = width
        self._height = height
        self._submitted_frames = 0

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def submit_rgba(self, data: bytes, width: int, height: int) -> None:
        """Submit one RGBA frame through the Piomatter framebuffer."""

        if width != self._width or height != self._height:
            raise ValueError(
                "Piomatter backend expected frame geometry "
                f"{self._width}x{self._height}, received {width}x{height}."
            )
        rgba = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        self._framebuffer[:, :, :] = rgba[:, :, :3]
        self._matrix.show()
        self._submitted_frames += 1

    def clear(self) -> None:
        """Clear the active framebuffer and present black."""

        self._framebuffer[:, :, :] = 0
        self._matrix.show()

    def CreateFrameCanvas(self) -> PiomatterFrameCanvas:
        """Create an offscreen RGBA canvas compatible with the worker API."""

        return PiomatterFrameCanvas.create(self._width, self._height)

    def SwapOnVSync(self, frame_canvas: object) -> PiomatterFrameCanvas:
        """Present an offscreen canvas and recycle it."""

        canvas = cast(PiomatterFrameCanvas, frame_canvas)
        self.submit_rgba(canvas.image.tobytes(), canvas.width, canvas.height)
        canvas.Clear()
        return canvas

    def stats(self) -> object:
        """Return lightweight runtime stats for parity with the native driver."""

        return SimpleNamespace(
            width=self._width,
            height=self._height,
            dropped_frames=0,
            rendered_frames=self._submitted_frames,
            refresh_hz_estimate=0.0,
            backend_name="piomatter",
        )

    def close(self) -> None:
        """Piomatter cleanup is implicit; keep the protocol surface consistent."""

        logger.debug("Closing Piomatter matrix driver.")
