"""Filesystem helpers for driver updates."""

import shutil
from pathlib import Path

from heart.manage.driver_update.exceptions import UpdateError
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def copy_file(source: Path, destination: Path) -> None:
    try:
        logger.info("Before copying: %s to %s", source, destination)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        logger.info("After copying: %s to %s", source, destination)
    except (OSError, shutil.Error):
        logger.exception("Failed to copy %s to %s", source, destination)


def ensure_driver_files(driver_path: Path) -> None:
    from heart.manage.driver_update.layout import DRIVER_FILES

    missing = [
        name for name in DRIVER_FILES if not (driver_path / name).exists()
    ]
    if missing:
        message = f"Missing driver files in {driver_path}: {', '.join(missing)}"
        logger.error(message)
        raise UpdateError(message)
