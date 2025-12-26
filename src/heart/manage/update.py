import sys

from heart.manage.driver_update.configuration import load_driver_config
from heart.manage.driver_update.exceptions import UpdateError
from heart.manage.driver_update.filesystem import ensure_driver_files
from heart.manage.driver_update.layout import DRIVER_SETTINGS_FILENAME
from heart.manage.driver_update.mounts import (circuitpy_mounts,
                                               install_uf2_if_available,
                                               mount_points,
                                               update_circuitpy_mount)
from heart.manage.driver_update.paths import get_driver_path, media_directory
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def main(device_driver_name: str) -> None:
    code_path = get_driver_path(device_driver_name)
    config = load_driver_config(code_path / DRIVER_SETTINGS_FILENAME)
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
