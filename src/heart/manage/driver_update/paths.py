"""Path resolution helpers for driver updates."""

from pathlib import Path

import heart
from heart.manage.driver_update.exceptions import UpdateError
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def media_directory() -> Path:
    if Configuration.is_pi():
        return Path("/media/michael")
    return Path("/Volumes")


def driver_base_path() -> Path:
    return Path(heart.__file__).resolve().parents[2] / "drivers"


def get_driver_path(device_driver_name: str) -> Path:
    code_path = driver_base_path() / device_driver_name
    if not code_path.is_dir():
        message = (
            "The path "
            f"{code_path} does not exist. This is where we expect the driver code to exist."
        )
        logger.error(message)
        raise UpdateError(message)
    return code_path
