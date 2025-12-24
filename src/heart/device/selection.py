import os

from heart.device import Cube, Device, Orientation, Rectangle
from heart.device.local import LocalScreen
from heart.utilities.env import Configuration, DeviceLayoutMode
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def select_device(*, x11_forward: bool) -> Device:
    layout_mode = Configuration.device_layout_mode()
    orientation: Orientation
    if layout_mode == DeviceLayoutMode.CUBE:
        orientation: Orientation = Cube.sides()
    else:
        orientation = Rectangle.with_layout(
            columns=Configuration.device_layout_columns(),
            rows=Configuration.device_layout_rows(),
        )
    panel_width = Configuration.panel_columns()
    panel_height = Configuration.panel_rows()

    if Configuration.forward_to_beats_app():
        from heart.device.beats import StreamedScreen

        return StreamedScreen(orientation=orientation)

    if Configuration.use_isolated_renderer():
        if x11_forward:
            logger.warning("USE_ISOLATED_RENDERER enabled; ignoring x11_forward flag")
        from heart.device.rgb_display import LEDMatrix

        return LEDMatrix(orientation=orientation)

    if Configuration.is_pi():
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

    return LocalScreen(width=panel_width, height=panel_height, orientation=orientation)
