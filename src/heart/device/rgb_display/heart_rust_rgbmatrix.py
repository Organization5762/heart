"""Opt-in rgbmatrix-style compatibility layer backed by the Heart Rust runtime.

This module intentionally does not replace the external ``rgbmatrix`` package.
Instead it gives Heart code a separate import path that presents the familiar
``RGBMatrixOptions`` / ``RGBMatrix`` surface while routing frames through the
clean-room ``heart_rust`` driver stack.

Only the subset of options that the clean-room runtime can express today are
mapped into the native config. Legacy rgbmatrix knobs that are transport- or
timing-specific for hzeller's implementation are accepted for compatibility and
logged when callers override them, but they are not applied by the Rust driver.
"""

from __future__ import annotations

from typing import Any, Final

from heart.utilities.logging import get_logger

from .runtime import _load_matrix_runtime_module

logger = get_logger(__name__)

DEFAULT_BRIGHTNESS: Final[int] = 100
DEFAULT_CHAIN_LENGTH: Final[int] = 1
DEFAULT_COLS: Final[int] = 32
DEFAULT_DISABLE_HARDWARE_PULSING: Final[bool] = False
DEFAULT_DROP_PRIVILEGES: Final[bool] = True
DEFAULT_GPIO_SLOWDOWN: Final[int] = 1
DEFAULT_HARDWARE_MAPPING: Final[str] = "adafruit-hat-pwm"
DEFAULT_LED_RGB_SEQUENCE: Final[str] = "RGB"
DEFAULT_MULTIPLEXING: Final[int] = 0
DEFAULT_PANEL_TYPE: Final[str] = ""
DEFAULT_PARALLEL: Final[int] = 1
DEFAULT_PIXEL_MAPPER_CONFIG: Final[str] = ""
DEFAULT_PWM_BITS: Final[int] = 11
DEFAULT_PWM_LSB_NANOSECONDS: Final[int] = 130
DEFAULT_ROW_ADDRESS_TYPE: Final[int] = 0
DEFAULT_ROWS: Final[int] = 32

HARDWARE_MAPPING_TO_WIRING_ATTR: Final[dict[str, str]] = {
    "adafruit-hat": "AdafruitHat",
    "adafruit-hat-pwm": "AdafruitHatPwm",
}
LED_RGB_SEQUENCE_TO_COLOR_ORDER_ATTR: Final[dict[str, str]] = {
    "GBR": "GBR",
    "RGB": "RGB",
}
IGNORED_OPTION_DEFAULTS: Final[dict[str, object]] = {
    "brightness": DEFAULT_BRIGHTNESS,
    "disable_hardware_pulsing": DEFAULT_DISABLE_HARDWARE_PULSING,
    "drop_privileges": DEFAULT_DROP_PRIVILEGES,
    "gpio_slowdown": DEFAULT_GPIO_SLOWDOWN,
    "multiplexing": DEFAULT_MULTIPLEXING,
    "panel_type": DEFAULT_PANEL_TYPE,
    "pixel_mapper_config": DEFAULT_PIXEL_MAPPER_CONFIG,
    "pwm_bits": DEFAULT_PWM_BITS,
    "pwm_lsb_nanoseconds": DEFAULT_PWM_LSB_NANOSECONDS,
    "row_address_type": DEFAULT_ROW_ADDRESS_TYPE,
}


class RGBMatrixOptions:
    """Mutable option bag that mirrors the common rgbmatrix constructor shape."""

    def __init__(self) -> None:
        self.hardware_mapping = DEFAULT_HARDWARE_MAPPING
        self.rows = DEFAULT_ROWS
        self.cols = DEFAULT_COLS
        self.chain_length = DEFAULT_CHAIN_LENGTH
        self.parallel = DEFAULT_PARALLEL
        self.row_address_type = DEFAULT_ROW_ADDRESS_TYPE
        self.multiplexing = DEFAULT_MULTIPLEXING
        self.pwm_bits = DEFAULT_PWM_BITS
        self.brightness = DEFAULT_BRIGHTNESS
        self.pwm_lsb_nanoseconds = DEFAULT_PWM_LSB_NANOSECONDS
        self.led_rgb_sequence = DEFAULT_LED_RGB_SEQUENCE
        self.pixel_mapper_config = DEFAULT_PIXEL_MAPPER_CONFIG
        self.panel_type = DEFAULT_PANEL_TYPE
        self.gpio_slowdown = DEFAULT_GPIO_SLOWDOWN
        self.disable_hardware_pulsing = DEFAULT_DISABLE_HARDWARE_PULSING
        self.drop_privileges = DEFAULT_DROP_PRIVILEGES


class RGBMatrix:
    """rgbmatrix-style wrapper that submits frames through ``heart_rust``."""

    def __init__(self, options: RGBMatrixOptions | None = None) -> None:
        self.options = options or RGBMatrixOptions()
        native_module = _load_matrix_runtime_module()
        _log_ignored_option_overrides(self.options)
        config = native_module.MatrixConfig(
            wiring=_resolve_wiring(native_module, self.options.hardware_mapping),
            panel_rows=self.options.rows,
            panel_cols=self.options.cols,
            chain_length=self.options.chain_length,
            parallel=self.options.parallel,
            color_order=_resolve_color_order(
                native_module, self.options.led_rgb_sequence
            ),
        )
        self._driver = native_module.MatrixDriver(config)

    @property
    def width(self) -> int:
        return self._driver.width

    @property
    def height(self) -> int:
        return self._driver.height

    def CreateFrameCanvas(self) -> object:
        return self._driver.CreateFrameCanvas()

    def SwapOnVSync(self, frame_canvas: object) -> object:
        return self._driver.SwapOnVSync(frame_canvas)

    def Clear(self) -> None:
        self._driver.clear()

    def stats(self) -> object:
        return self._driver.stats()

    def close(self) -> None:
        self._driver.close()


def _resolve_wiring(native_module: Any, hardware_mapping: str) -> object:
    wiring_attr = HARDWARE_MAPPING_TO_WIRING_ATTR.get(hardware_mapping)
    if wiring_attr is None:
        supported = ", ".join(sorted(HARDWARE_MAPPING_TO_WIRING_ATTR))
        raise ValueError(
            "heart_rust RGBMatrix compatibility only supports hardware mappings "
            f"{supported}; received {hardware_mapping!r}."
        )
    return getattr(native_module.WiringProfile, wiring_attr)


def _resolve_color_order(native_module: Any, led_rgb_sequence: str) -> object:
    color_order_attr = LED_RGB_SEQUENCE_TO_COLOR_ORDER_ATTR.get(
        led_rgb_sequence.upper()
    )
    if color_order_attr is None:
        supported = ", ".join(sorted(LED_RGB_SEQUENCE_TO_COLOR_ORDER_ATTR))
        raise ValueError(
            "heart_rust RGBMatrix compatibility only supports LED RGB sequences "
            f"{supported}; received {led_rgb_sequence!r}."
        )
    return getattr(native_module.ColorOrder, color_order_attr)


def _log_ignored_option_overrides(options: RGBMatrixOptions) -> None:
    ignored_overrides = [
        f"{option_name}={getattr(options, option_name)!r}"
        for option_name, default_value in IGNORED_OPTION_DEFAULTS.items()
        if getattr(options, option_name) != default_value
    ]
    if ignored_overrides:
        logger.warning(
            "heart_rust RGBMatrix compatibility ignores legacy rgbmatrix options "
            "that the clean-room runtime does not implement yet: %s",
            ", ".join(ignored_overrides),
        )
