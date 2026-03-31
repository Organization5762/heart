from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from heart.device.rgb_display.constants import \
        DEFAULT_SOCKET_PATH as DEFAULT_SOCKET_PATH
    from heart.device.rgb_display.device import LEDMatrix as LEDMatrix
    from heart.device.rgb_display.heart_rust_rgbmatrix import \
        RGBMatrix as RGBMatrix
    from heart.device.rgb_display.heart_rust_rgbmatrix import \
        RGBMatrixOptions as RGBMatrixOptions
    from heart.device.rgb_display.sample_base import SampleBase as SampleBase
    from heart.device.rgb_display.worker import \
        MatrixDisplayWorker as MatrixDisplayWorker

    HeartRustRGBMatrix = RGBMatrix
    HeartRustRGBMatrixOptions = RGBMatrixOptions


def __getattr__(name: str) -> Any:
    if name == "LEDMatrix":
        from heart.device.rgb_display.device import LEDMatrix

        return LEDMatrix
    if name == "DEFAULT_SOCKET_PATH":
        from heart.device.rgb_display.constants import DEFAULT_SOCKET_PATH

        return DEFAULT_SOCKET_PATH
    if name == "HeartRustRGBMatrix":
        from heart.device.rgb_display.heart_rust_rgbmatrix import RGBMatrix

        return RGBMatrix
    if name == "HeartRustRGBMatrixOptions":
        from heart.device.rgb_display.heart_rust_rgbmatrix import \
            RGBMatrixOptions

        return RGBMatrixOptions
    if name == "SampleBase":
        from heart.device.rgb_display.sample_base import SampleBase

        return SampleBase
    if name == "MatrixDisplayWorker":
        from heart.device.rgb_display.worker import MatrixDisplayWorker

        return MatrixDisplayWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
