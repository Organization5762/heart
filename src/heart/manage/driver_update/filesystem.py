"""Filesystem helpers for driver updates."""

import shutil
import subprocess
from pathlib import Path

from heart import firmware_io
from heart.manage.driver_update.downloads import download_file
from heart.manage.driver_update.exceptions import UpdateError
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

CIRCUIT_PY_COMMON_LIBS_UNZIPPED_NAME = (
    "adafruit-circuitpython-bundle-9.x-mpy-20250412"
)
CIRCUIT_PY_COMMON_LIBS = (
    "https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/download/"
    f"20250412/{CIRCUIT_PY_COMMON_LIBS_UNZIPPED_NAME}.zip"
)
CIRCUIT_PY_COMMON_LIBS_CHECKSUM = (
    "6d49c73c352da31d5292508ff9b3eca2803372c1d2acca7175b64be2ff2bc450"
)
DRIVER_SETTINGS_FILENAME = "settings.toml"
DRIVER_FILES = ("boot.py", "code.py", DRIVER_SETTINGS_FILENAME)


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
    missing = [
        name for name in DRIVER_FILES if not (driver_path / name).exists()
    ]
    if missing:
        message = f"Missing driver files in {driver_path}: {', '.join(missing)}"
        logger.error(message)
        raise UpdateError(message)


def load_driver_libs(libs: list[str], destination: Path) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    copy_file(
        Path(firmware_io.__file__).parent,
        destination.joinpath(*firmware_io.__package__.split(".")),
    )

    if not libs:
        logger.info("Skipping loading driver libs as no libs were requested.")
        return

    logger.info("Loading the following libs: %s", libs)
    zip_location = download_file(
        CIRCUIT_PY_COMMON_LIBS, CIRCUIT_PY_COMMON_LIBS_CHECKSUM
    )
    unzipped_location = zip_location.with_suffix("")
    lib_path = unzipped_location / "lib"

    if not lib_path.exists():
        subprocess.run(
            ["unzip", str(zip_location)],
            check=True,
            cwd=str(unzipped_location.parent),
        )
    else:
        logger.info(
            "Skipping unzipping %s because %s exists", zip_location, lib_path
        )

    for lib in libs:
        copy_file(lib_path / lib, destination / lib)
        mpy_source = lib_path / f"{lib}.mpy"
        if mpy_source.exists():
            copy_file(mpy_source, destination / f"{lib}.mpy")
        else:
            logger.warning("Skipping missing %s", mpy_source)
