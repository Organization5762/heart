import os
from pathlib import Path

from heart.device import Cube, Device, Orientation, Rectangle
from heart.device.beats.device import StreamedScreen
from heart.device.local import LocalScreen
from heart.device.rgb_display.device import LEDMatrix
from heart.utilities.env import Configuration, DeviceLayoutMode
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
RP1_HUB75_DEVICE_PATH = Path("/dev/rp1-hub75")
PI5_MATRIX_BACKEND_ENV_VAR = "HEART_PI5_MATRIX_BACKEND"


def select_device() -> Device:
    orientation = _select_orientation()
    panel_width = Configuration.panel_columns()
    panel_height = Configuration.panel_rows()

    streamed_device = _select_streamed_device(orientation)
    if streamed_device is not None:
        return streamed_device

    isolated_device = _select_isolated_renderer_device(orientation=orientation)
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

    if orientation.get_type() is not Cube:
        logger.info(
            "Forcing Beats streamed device layout to cube sides so the totem atlas stays 4x1. requested_layout=%s",
            orientation.layout,
        )
    return StreamedScreen(orientation=Cube.sides())


def _select_isolated_renderer_device(*, orientation: Orientation) -> Device | None:
    if not Configuration.use_isolated_renderer():
        return None

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
        return _select_pi_local_screen(
            orientation=orientation,
            panel_width=panel_width,
            panel_height=panel_height,
            reason="X11_FORWARD set",
        )

    if (
        pi_info is not None
        and pi_info.version >= 5
        and not _rp1_hub75_device_exists()
        and not _pi5_matrix_backend_requested()
    ):
        return _select_pi_local_screen(
            orientation=orientation,
            panel_width=panel_width,
            panel_height=panel_height,
            reason=(
                f"{RP1_HUB75_DEVICE_PATH} is not present and "
                f"{PI5_MATRIX_BACKEND_ENV_VAR} is not set"
            ),
        )

    try:
        return LEDMatrix(orientation=orientation)
    except RuntimeError as exc:
        if _is_missing_native_matrix_runtime(exc):
            return _select_pi_local_screen(
                orientation=orientation,
                panel_width=panel_width,
                panel_height=panel_height,
                reason=str(exc),
            )
        raise


def _rp1_hub75_device_exists() -> bool:
    return RP1_HUB75_DEVICE_PATH.exists()


def _pi5_matrix_backend_requested() -> bool:
    value = os.environ.get(PI5_MATRIX_BACKEND_ENV_VAR, "").strip().lower()
    return value not in {"", "auto"}


def _is_missing_native_matrix_runtime(error: RuntimeError) -> bool:
    return "heart-rgb-matrix-driver" in str(error)


def _select_pi_local_screen(
    *,
    orientation: Orientation,
    panel_width: int,
    panel_height: int,
    reason: str,
) -> LocalScreen:
    os.environ["X11_FORWARD"] = "1"
    logger.warning("%s; running with LocalScreen.", reason)
    return LocalScreen(
        width=panel_width,
        height=panel_height,
        orientation=orientation,
    )
