"""Helpers for the clean-room HUB75 runtime integration."""

from __future__ import annotations

from types import ModuleType
from typing import Protocol, cast

from heart.device import Orientation
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import

MATRIX_RUNTIME_MODULE = "heart_rust"

logger = get_logger(__name__)


class MatrixDriverProtocol(Protocol):
    @property
    def width(self) -> int:
        """Return the logical display width in pixels."""

    @property
    def height(self) -> int:
        """Return the logical display height in pixels."""

    def submit_rgba(self, data: bytes, width: int, height: int) -> None:
        """Submit an RGBA frame to the runtime."""

    def clear(self) -> None:
        """Clear the active frame."""

    def CreateFrameCanvas(self) -> object:
        """Return an offscreen canvas compatible with the common rgbmatrix API."""

    def SwapOnVSync(self, frame_canvas: object) -> object:
        """Present an offscreen canvas and return the next reusable canvas."""

    def stats(self) -> object:
        """Return runtime stats for the active driver."""

    def close(self) -> None:
        """Shut down the runtime."""


def build_matrix_driver(orientation: Orientation) -> MatrixDriverProtocol:
    native_module = _load_matrix_runtime_module()
    config = build_matrix_config(native_module, orientation)
    driver_type = getattr(native_module, "MatrixDriver", None)
    if driver_type is None:
        raise RuntimeError(
            f"Native matrix runtime module {MATRIX_RUNTIME_MODULE} is missing MatrixDriver."
        )
    return cast(MatrixDriverProtocol, driver_type(config))


def build_matrix_config(native_module: ModuleType, orientation: Orientation) -> object:
    config_type = getattr(native_module, "MatrixConfig", None)
    wiring_profile = getattr(native_module, "WiringProfile", None)
    color_order = getattr(native_module, "ColorOrder", None)
    if config_type is None or wiring_profile is None or color_order is None:
        raise RuntimeError(
            f"Native matrix runtime module {MATRIX_RUNTIME_MODULE} is missing configuration types."
        )
    return config_type(
        wiring=wiring_profile.AdafruitHatPwm,
        panel_rows=Configuration.panel_rows(),
        panel_cols=Configuration.panel_columns(),
        chain_length=orientation.layout.columns,
        parallel=orientation.layout.rows,
        color_order=color_order.RGB,
    )


def _load_matrix_runtime_module() -> ModuleType:
    native_module = optional_import(MATRIX_RUNTIME_MODULE, logger=logger)
    if native_module is None:
        raise RuntimeError(
            "The clean-room HUB75 runtime is unavailable. Install the optional "
            "`heart-rust` package or sync the project with `uv sync --extra native`."
        )
    return cast(ModuleType, native_module)
