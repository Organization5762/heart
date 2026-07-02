"""Helpers for the clean-room HUB75 runtime integration."""

from __future__ import annotations

import os
from types import ModuleType
from typing import Protocol, cast

from heart.device import Orientation
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import

MATRIX_RUNTIME_MODULE = "heart_rgb_matrix_driver"
NATIVE_BACKEND = "native"
BACKEND_ENV_VAR = "HEART_RGB_DISPLAY_BACKEND"
HARDWARE_MAPPING_ENV_VAR = "HEART_RGB_MATRIX_HARDWARE_MAPPING"

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


class WiringProfileProtocol(Protocol):
    AdafruitHatPwm: object
    ElectroDragonP0: object
    ThreePortActive: object


class ColorOrderProtocol(Protocol):
    RGB: object


def build_matrix_driver(orientation: Orientation) -> MatrixDriverProtocol:
    backend_name = os.getenv(BACKEND_ENV_VAR, "").strip().lower()
    if backend_name not in ("", NATIVE_BACKEND):
        raise RuntimeError(
            f"Unsupported RGB display backend {backend_name!r}. Use {NATIVE_BACKEND!r}."
        )
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
    wiring_profile = cast(
        WiringProfileProtocol | None, getattr(native_module, "WiringProfile", None)
    )
    color_order = cast(
        ColorOrderProtocol | None, getattr(native_module, "ColorOrder", None)
    )
    if config_type is None or wiring_profile is None or color_order is None:
        raise RuntimeError(
            f"Native matrix runtime module {MATRIX_RUNTIME_MODULE} is missing configuration types."
        )
    hardware_mapping = os.environ.get(HARDWARE_MAPPING_ENV_VAR, "three-port-active")
    wiring = _resolve_wiring_profile(wiring_profile, hardware_mapping)
    if (
        wiring == wiring_profile.ThreePortActive
        and (orientation.layout.columns != 4 or orientation.layout.rows != 1)
    ):
        raise RuntimeError(
            "three-port-active requires a horizontal 4-panel layout so the RP1 "
            "driver receives a 256x64 RGB888 strip. Set HEART_LAYOUT_COLUMNS=4 "
            "and HEART_LAYOUT_ROWS=1."
        )
    return config_type(
        wiring=wiring,
        panel_rows=Configuration.panel_rows(),
        panel_cols=Configuration.panel_columns(),
        chain_length=orientation.layout.columns,
        parallel=orientation.layout.rows,
        color_order=color_order.RGB,
    )


def _resolve_wiring_profile(
    wiring_profile: WiringProfileProtocol, hardware_mapping: str
) -> object:
    match hardware_mapping:
        case "adafruit-hat-pwm" | "adafruit_hat_pwm":
            return wiring_profile.AdafruitHatPwm
        case "electrodragon" | "electrodragon-p0" | "electrodragon_p0":
            return wiring_profile.ElectroDragonP0
        case "regular" | "three-port-active" | "three_port_active":
            return wiring_profile.ThreePortActive
    raise RuntimeError(f"Unsupported {HARDWARE_MAPPING_ENV_VAR}={hardware_mapping!r}.")


def _load_matrix_runtime_module() -> ModuleType:
    native_module = optional_import(MATRIX_RUNTIME_MODULE, logger=logger)
    if native_module is None:
        raise RuntimeError(
            "The clean-room HUB75 runtime is unavailable. Install the optional "
            "`heart-rgb-matrix-driver` package with `make install` or `make pi_install`."
        )
    return cast(ModuleType, native_module)
