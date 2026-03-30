"""Path resolution helpers for driver updates."""

import os
from pathlib import Path

from heart_device_manager.driver_update.exceptions import UpdateError
from heart_device_manager.environment import is_pi
from heart_device_manager.logging import get_logger

DRIVER_ROOT_ENV_VAR = "HEART_DEVICE_MANAGER_DRIVER_ROOT"
DRIVERS_DIRECTORY_NAME = "drivers"

logger = get_logger(__name__)


def media_directory() -> Path:
    if is_pi():
        return Path("/media/michael")
    return Path("/Volumes")


def driver_base_path() -> Path:
    configured_root = os.environ.get(DRIVER_ROOT_ENV_VAR)
    if configured_root:
        return Path(configured_root).expanduser().resolve()

    package_path = Path(__file__).resolve()
    for base_path in package_path.parents:
        candidate = base_path / DRIVERS_DIRECTORY_NAME
        if candidate.is_dir():
            return candidate

    current_path = Path.cwd().resolve()
    for base_path in (current_path, *current_path.parents):
        candidate = base_path / DRIVERS_DIRECTORY_NAME
        if candidate.is_dir():
            return candidate

    return current_path / DRIVERS_DIRECTORY_NAME


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
