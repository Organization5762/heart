from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from heart.device.rgb_display.constants import \
        DEFAULT_SOCKET_PATH as DEFAULT_SOCKET_PATH
    from heart.device.rgb_display.device import LEDMatrix as LEDMatrix
    from heart.device.rgb_display.heart_rgb_matrix_driver_rgbmatrix import \
        RGBMatrix as RGBMatrix
    from heart.device.rgb_display.heart_rgb_matrix_driver_rgbmatrix import \
        RGBMatrixOptions as RGBMatrixOptions

    HeartRgbMatrixDriver = RGBMatrix
    HeartRgbMatrixDriverOptions = RGBMatrixOptions


def __getattr__(name: str) -> Any:
    if name == "LEDMatrix":
        from heart.device.rgb_display.device import LEDMatrix

        return LEDMatrix
    if name == "DEFAULT_SOCKET_PATH":
        from heart.device.rgb_display.constants import DEFAULT_SOCKET_PATH

        return DEFAULT_SOCKET_PATH
    if name == "HeartRgbMatrixDriver":
        from heart.device.rgb_display.heart_rgb_matrix_driver_rgbmatrix import \
            RGBMatrix

        return RGBMatrix
    if name == "HeartRgbMatrixDriverOptions":
        from heart.device.rgb_display.heart_rgb_matrix_driver_rgbmatrix import \
            RGBMatrixOptions

        return RGBMatrixOptions
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
