"""Python-facing matrix runtime API backed by the native Heart Rust package."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ._heart_rust import NativeMatrixDriver, NativeMatrixStats


class WiringProfile(StrEnum):
    AdafruitHatPwm = "adafruit_hat_pwm"
    AdafruitHat = "adafruit_hat"
    AdafruitTripleHat = "adafruit_triple_hat"


class ColorOrder(StrEnum):
    RGB = "rgb"
    GBR = "gbr"


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


class MatrixDriver:
    def __init__(self, config: MatrixConfig) -> None:
        self._driver = NativeMatrixDriver(
            config.wiring.value,
            config.panel_rows,
            config.panel_cols,
            config.chain_length,
            config.parallel,
            config.color_order.value,
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

    def stats(self) -> MatrixStats:
        return MatrixStats.from_native(self._driver.stats())

    def close(self) -> None:
        self._driver.close()
