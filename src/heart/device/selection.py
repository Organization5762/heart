import os

from heart.device import Cube, Device, Orientation, Rectangle
from heart.device.local import LocalScreen
from heart.utilities.env import Configuration, DeviceLayoutMode
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def select_device(*, x11_forward: bool) -> Device:
    orientation = _select_orientation()
    panel_width = Configuration.panel_columns()
    panel_height = Configuration.panel_rows()

    streamed_device = _select_streamed_device(orientation)
    if streamed_device is not None:
        return streamed_device

    isolated_device = _select_isolated_renderer_device(
        orientation=orientation,
        x11_forward=x11_forward,
    )
    if isolated_device is not None:
        return isolated_device

    pi_device = _select_pi_device(
        orientation=orientation,
        panel_width=panel_width,
        panel_height=panel_height,
    )
    if pi_device is not None:
        return pi_device

    return LocalScreen(width=panel_width, height=panel_height, orientation=orientation)


def _select_orientation() -> Orientation:
    layout_mode = Configuration.device_layout_mode()
    if layout_mode == DeviceLayoutMode.CUBE:
        return Cube.sides()
    return Rectangle.with_layout(
        columns=Configuration.device_layout_columns(),
        rows=Configuration.device_layout_rows(),
    )


def _select_streamed_device(orientation: Orientation) -> Device | None:
    if not Configuration.forward_to_beats_app():
        return None
    from heart.device.beats import StreamedScreen

    return StreamedScreen(orientation=orientation)


def _select_isolated_renderer_device(
    *, orientation: Orientation, x11_forward: bool
) -> Device | None:
    if not Configuration.use_isolated_renderer():
        return None
    if x11_forward:
        logger.warning("USE_ISOLATED_RENDERER enabled; ignoring x11_forward flag")
    from heart.device.rgb_display import LEDMatrix

    return LEDMatrix(orientation=orientation)


def _select_pi_device(
    *, orientation: Orientation, panel_width: int, panel_height: int
) -> Device | None:
    if not Configuration.is_pi():
        return None
    os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

    pi_info = Configuration.pi()
    if pi_info is not None and pi_info.version > 4:
        logger.warning(
            f"Shit not guaranteed to work Pi5 and higher. Detected: {pi_info}"
        )

    if Configuration.is_x11_forward():
        # This makes it work on Pi when no screens are connected.
        # You need to setup X11 forwarding with XQuartz to do that.
        logger.warning("X11_FORWARD set, running with `LocalScreen`")
        return LocalScreen(
            width=panel_width,
            height=panel_height,
            orientation=orientation,
        )

    from heart.device.rgb_display import LEDMatrix

    return LEDMatrix(orientation=orientation)
