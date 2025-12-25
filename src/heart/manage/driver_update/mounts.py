"""Mount discovery and update logic for driver updates."""

import time
from pathlib import Path

from heart.manage.driver_update.configuration import DriverConfig
from heart.manage.driver_update.downloads import download_file
from heart.manage.driver_update.exceptions import UpdateError
from heart.manage.driver_update.filesystem import (DRIVER_FILES, copy_file,
                                                   load_driver_libs)
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
UF2_INSTALL_DELAY_SECONDS = 10


def mount_points(media_directory: Path) -> list[Path]:
    if not media_directory.is_dir():
        message = (
            f"Expected media directory {media_directory} to exist before updates."
        )
        logger.error(message)
        raise UpdateError(message)

    return [
        entry for entry in media_directory.iterdir() if entry.is_dir()
    ]


def install_uf2_if_available(
    config: DriverConfig, *, media_directory: Path
) -> None:
    uf2_destination = media_directory / config.device_boot_name
    if uf2_destination.is_dir():
        downloaded_file_path = download_file(config.uf2_url, config.uf2_checksum)
        copy_file(downloaded_file_path, uf2_destination)
        time.sleep(UF2_INSTALL_DELAY_SECONDS)
    else:
        logger.info(
            "Skipping CircuitPython UF2 installation as no device is in boot mode currently"
        )


def circuitpy_mounts(
    mount_points: list[Path], *, media_directory: Path
) -> list[Path]:
    circuitpy_mounts = [
        mount_point
        for mount_point in mount_points
        if "CIRCUITPY" in mount_point.name
    ]
    if not circuitpy_mounts:
        logger.warning("No CIRCUITPY volumes found under %s.", media_directory)
    return circuitpy_mounts


def _parse_board_id(boot_out_path: Path) -> str:
    with boot_out_path.open("r", encoding="utf-8") as file_handle:
        for line in file_handle:
            if "Board ID:" in line:
                return line.split("Board ID:")[1].strip()
    raise ValueError(f"Unable to find Board ID identifier in {boot_out_path}")


def update_circuitpy_mount(
    media_location: Path, config: DriverConfig, code_path: Path
) -> None:
    boot_out_path = media_location / "boot_out.txt"
    if not boot_out_path.exists():
        logger.info("%s is missing, skipping...", boot_out_path)
        return

    try:
        board_id = _parse_board_id(boot_out_path)
    except ValueError as error:
        logger.warning("Unable to parse board ID: %s", error)
        return

    if board_id not in config.valid_board_ids:
        logger.info(
            "Skipping: The board ID %s is not in the list of valid board IDs: %s",
            board_id,
            config.valid_board_ids,
        )
        return

    for file_name in DRIVER_FILES:
        copy_file(
            code_path / file_name,
            media_location / file_name,
        )

    load_driver_libs(
        libs=config.driver_libs,
        destination=media_location / "lib",
    )
