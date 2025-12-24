from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from heart.device.rgb_display.device import LEDMatrix as LEDMatrix
    from heart.device.rgb_display.isolated_render import \
        DEFAULT_SOCKET_PATH as DEFAULT_SOCKET_PATH
    from heart.device.rgb_display.isolated_render import \
        MatrixClient as MatrixClient
    from heart.device.rgb_display.sample_base import SampleBase as SampleBase
    from heart.device.rgb_display.worker import \
        MatrixDisplayWorker as MatrixDisplayWorker


def __getattr__(name: str) -> Any:
    if name == "LEDMatrix":
        from heart.device.rgb_display.device import LEDMatrix

        return LEDMatrix
    if name == "DEFAULT_SOCKET_PATH":
        from heart.device.rgb_display.isolated_render import \
            DEFAULT_SOCKET_PATH

        return DEFAULT_SOCKET_PATH
    if name == "MatrixClient":
        from heart.device.rgb_display.isolated_render import MatrixClient

        return MatrixClient
    if name == "SampleBase":
        from heart.device.rgb_display.sample_base import SampleBase

        return SampleBase
    if name == "MatrixDisplayWorker":
        from heart.device.rgb_display.worker import MatrixDisplayWorker

        return MatrixDisplayWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
