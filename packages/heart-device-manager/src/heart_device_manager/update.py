import sys

from heart_device_manager.driver_update.arduino import update_arduino_sketch
from heart_device_manager.driver_update.configuration import load_driver_config
from heart_device_manager.driver_update.exceptions import UpdateError
from heart_device_manager.driver_update.filesystem import ensure_driver_files
from heart_device_manager.driver_update.layout import DRIVER_SETTINGS_FILENAME
from heart_device_manager.driver_update.modes import UpdateMode
from heart_device_manager.driver_update.mounts import (
    circuitpy_mounts, install_uf2_if_available, mount_points,
    update_circuitpy_mount)
from heart_device_manager.driver_update.paths import (get_driver_path,
                                                      media_directory)
from heart_device_manager.logging import get_logger

logger = get_logger(__name__)


def resolve_update_mode(
    *, requested_mode: UpdateMode, config_default: UpdateMode
) -> UpdateMode:
    """Resolve the effective driver update mode."""

    if requested_mode == UpdateMode.AUTO:
        return config_default
    return requested_mode


def main(
    device_driver_name: str, *, mode: UpdateMode = UpdateMode.AUTO
) -> None:
    code_path = get_driver_path(device_driver_name)
    config = load_driver_config(code_path / DRIVER_SETTINGS_FILENAME)
    resolved_mode = resolve_update_mode(
        requested_mode=mode, config_default=config.default_update_mode
    )
    if resolved_mode == UpdateMode.ARDUINO:
        update_arduino_sketch(config)
        return

    ensure_driver_files(code_path)
    media_root = media_directory()
    detected_mount_points = mount_points(media_root)
    install_uf2_if_available(config, media_directory=media_root)
    for media_location in circuitpy_mounts(
        detected_mount_points, media_directory=media_root
    ):
        update_circuitpy_mount(media_location, config, code_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error(
            "DEVICE_DRIVER_NAME is not set. Please supply it as the first argument."
        )
        sys.exit(1)

    if not sys.argv[1]:
        logger.error(
            "DEVICE_DRIVER_NAME is not set. Please supply it as the first argument."
        )
        sys.exit(1)
    try:
        main(sys.argv[1])
    except UpdateError:
        sys.exit(1)
