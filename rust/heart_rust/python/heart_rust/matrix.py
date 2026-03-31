"""Python-facing matrix runtime API backed by the native Heart Rust package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PIL import Image

from ._heart_rust import ColorOrder, NativeMatrixDriver, NativeMatrixStats, WiringProfile

RGBA_IMAGE_FORMAT: Final[str] = "RGBA"


@dataclass(frozen=True)
class MatrixConfig:
    wiring: WiringProfile
    panel_rows: int
    panel_cols: int
    chain_length: int
    parallel: int
    color_order: ColorOrder


@dataclass(frozen=True)
class MatrixStats:
    width: int
    height: int
    dropped_frames: int
    rendered_frames: int
    refresh_hz_estimate: float
    backend_name: str

    @classmethod
    def from_native(cls, native_stats: NativeMatrixStats) -> "MatrixStats":
        return cls(
            width=native_stats.width,
            height=native_stats.height,
            dropped_frames=native_stats.dropped_frames,
            rendered_frames=native_stats.rendered_frames,
            refresh_hz_estimate=native_stats.refresh_hz_estimate,
            backend_name=native_stats.backend_name,
        )


class FrameCanvas:
    """Offscreen canvas compatible with the common rgbmatrix Python calling shape."""

    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self._image = Image.new(RGBA_IMAGE_FORMAT, (width, height), (0, 0, 0, 255))

    def Clear(self) -> None:
        self._image.paste((0, 0, 0, 255), (0, 0, self._width, self._height))

    def SetImage(self, image: Image.Image, offset_x: int, offset_y: int) -> None:
        converted_image = image.convert(RGBA_IMAGE_FORMAT)
        self._image.paste(converted_image, (offset_x, offset_y), converted_image)

    def rgba_bytes(self) -> bytes:
        return self._image.tobytes()


class MatrixDriver:
    def __init__(self, config: MatrixConfig) -> None:
        self._driver = NativeMatrixDriver(
            config.wiring,
            config.panel_rows,
            config.panel_cols,
            config.chain_length,
            config.parallel,
            config.color_order,
        )

    @property
    def width(self) -> int:
        return self._driver.width

    @property
    def height(self) -> int:
        return self._driver.height

    def submit_rgba(self, data: bytes, width: int, height: int) -> None:
        self._driver.submit_rgba(data, width, height)

    def clear(self) -> None:
        self._driver.clear()

    def CreateFrameCanvas(self) -> FrameCanvas:
        return FrameCanvas(self.width, self.height)

    def SwapOnVSync(self, frame_canvas: FrameCanvas) -> FrameCanvas:
        self.submit_rgba(frame_canvas.rgba_bytes(), self.width, self.height)
        return frame_canvas

    def stats(self) -> MatrixStats:
        return MatrixStats.from_native(self._driver.stats())

    def close(self) -> None:
        self._driver.close()
