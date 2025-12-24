import hashlib
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import toml

import heart
import heart.firmware_io
from heart import firmware_io
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

if Configuration.is_pi():
    MEDIA_DIRECTORY = "/media/michael"
else:
    MEDIA_DIRECTORY = "/Volumes"

CIRCUIT_PY_COMMON_LIBS_UNZIPPED_NAME = "adafruit-circuitpython-bundle-9.x-mpy-20250412"
CIRCUIT_PY_COMMON_LIBS = (
    "https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/download/"
    f"20250412/{CIRCUIT_PY_COMMON_LIBS_UNZIPPED_NAME}.zip"
)
CIRCUIT_PY_COMMON_LIBS_CHECKSUM = (
    "6d49c73c352da31d5292508ff9b3eca2803372c1d2acca7175b64be2ff2bc450"
)
DRIVER_SETTINGS_FILENAME = "settings.toml"
DRIVER_FILES = ("boot.py", "code.py", DRIVER_SETTINGS_FILENAME)


@dataclass(frozen=True)
class DriverConfig:
    uf2_url: str
    uf2_checksum: str
    driver_libs: list[str]
    device_boot_name: str
    valid_board_ids: list[str]


def load_driver_libs(libs: list[str], destination: str) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    os.makedirs(destination, exist_ok=True)
    # Our local lib
    copy_file(
        os.path.dirname(firmware_io.__file__),
        os.path.join(destination, *firmware_io.__package__.split(".")),
    )

    if not libs:
        logger.info("Skipping loading driver libs as no libs were requested.")
        return

    logger.info("Loading the following libs: %s", libs)
    zip_location = download_file(
        CIRCUIT_PY_COMMON_LIBS, CIRCUIT_PY_COMMON_LIBS_CHECKSUM
    )
    unzipped_location = zip_location.replace(".zip", "")
    # Lib in this case just comes from the downloaded file, which is separate from the `destination` which is also lib
    lib_path = os.path.join(unzipped_location, "lib")

    if not os.path.exists(lib_path):
        subprocess.run(
            ["unzip", zip_location], check=True, cwd=os.path.dirname(unzipped_location)
        )
    else:
        logger.info(
            "Skipping unzipping %s because %s exists", zip_location, lib_path
        )

    for lib in libs:
        copy_file(os.path.join(lib_path, lib), os.path.join(destination, lib))
        # There are also .mpy files..
        mpy_source = os.path.join(lib_path, f"{lib}.mpy")
        if os.path.exists(mpy_source):
            copy_file(mpy_source, os.path.join(destination, f"{lib}.mpy"))
        else:
            logger.warning("Skipping missing %s", mpy_source)


def _sha256sum(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, checksum: str) -> str:
    try:
        destination = os.path.join("/tmp", url.split("/")[-1])
        if os.path.exists(destination):
            existing_checksum = _sha256sum(destination)
            if existing_checksum != checksum:
                logger.warning(
                    "Removing %s; checksum %s did not match %s.",
                    destination,
                    existing_checksum,
                    checksum,
                )
                os.remove(destination)

        if not os.path.exists(destination):
            logger.info("Starting download: %s", url)
            if Configuration.is_pi():
                subprocess.run(["wget", url, "-O", destination], check=True)
            else:
                subprocess.run(["curl", "-fL", url, "-o", destination], check=True)
            logger.info("Finished download: %s", destination)

        downloaded_checksum = _sha256sum(destination)
        logger.info("Checksum for %s: %s", destination, downloaded_checksum)
        if downloaded_checksum != checksum:
            logger.error(
                "Checksum mismatch for %s. Expected %s, but got %s.",
                destination,
                checksum,
                downloaded_checksum,
            )
            sys.exit(1)
        logger.info("Checksum matches expectations.")
        return destination
    except subprocess.CalledProcessError:
        logger.error("Failed to download %s", url)
        sys.exit(1)


def copy_file(source: str, destination: str) -> None:
    try:
        logger.info("Before copying: %s to %s", source, destination)
        if os.path.isdir(source):
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copy2(source, destination)
        logger.info("After copying: %s to %s", source, destination)
    except (OSError, shutil.Error) as error:
        logger.error("Failed to copy %s to %s: %s", source, destination, error)


def _parse_csv(value: str | list[str], *, field_name: str) -> list[str]:
    if isinstance(value, list):
        entries = [str(entry).strip() for entry in value]
    elif isinstance(value, str):
        entries = [entry.strip() for entry in value.split(",")]
    else:
        raise ValueError(
            f"Expected {field_name} to be a list or comma-delimited string, got {type(value)!r}"
        )

    return [entry for entry in entries if entry]


def _require_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Expected {field_name} to be a non-empty string, got {value!r}"
        )
    return value


def _load_driver_config(settings_path: str) -> DriverConfig:
    try:
        config = toml.load(settings_path)
    except (FileNotFoundError, toml.TomlDecodeError) as error:
        logger.error("Unable to read driver settings at %s: %s", settings_path, error)
        sys.exit(1)

    missing = [
        key
        for key in (
            "CIRCUIT_PY_UF2_URL",
            "CIRCUIT_PY_UF2_CHECKSUM",
            "CIRCUIT_PY_DRIVER_LIBS",
            "CIRCUIT_PY_BOOT_NAME",
            "VALID_BOARD_IDS",
        )
        if key not in config
    ]
    if missing:
        logger.error(
            "Missing keys in %s: %s", settings_path, ", ".join(missing)
        )
        sys.exit(1)

    try:
        driver_libs = _parse_csv(
            config["CIRCUIT_PY_DRIVER_LIBS"],
            field_name="CIRCUIT_PY_DRIVER_LIBS",
        )
        valid_board_ids = _parse_csv(
            config["VALID_BOARD_IDS"],
            field_name="VALID_BOARD_IDS",
        )
        uf2_url = _require_string(
            config["CIRCUIT_PY_UF2_URL"], field_name="CIRCUIT_PY_UF2_URL"
        )
        uf2_checksum = _require_string(
            config["CIRCUIT_PY_UF2_CHECKSUM"], field_name="CIRCUIT_PY_UF2_CHECKSUM"
        )
        device_boot_name = _require_string(
            config["CIRCUIT_PY_BOOT_NAME"], field_name="CIRCUIT_PY_BOOT_NAME"
        )
    except ValueError as error:
        logger.error("Invalid driver settings in %s: %s", settings_path, error)
        sys.exit(1)

    return DriverConfig(
        uf2_url=uf2_url,
        uf2_checksum=uf2_checksum,
        driver_libs=driver_libs,
        device_boot_name=device_boot_name,
        valid_board_ids=valid_board_ids,
    )


def _parse_board_id(boot_out_path: str) -> str:
    with open(boot_out_path, "r") as file_handle:
        for line in file_handle:
            if "Board ID:" in line:
                return line.split("Board ID:")[1].strip()
    raise ValueError(f"Unable to find Board ID identifier in {boot_out_path}")


def _ensure_driver_files(driver_path: str) -> None:
    missing = [
        name
        for name in DRIVER_FILES
        if not os.path.exists(os.path.join(driver_path, name))
    ]
    if missing:
        logger.error(
            "Missing driver files in %s: %s", driver_path, ", ".join(missing)
        )
        sys.exit(1)


def _mount_points(media_directory: str) -> list[str]:
    if not os.path.isdir(media_directory):
        logger.error(
            "Expected media directory %s to exist before updates.", media_directory
        )
        sys.exit(1)

    return [
        os.path.join(media_directory, entry)
        for entry in os.listdir(media_directory)
        if os.path.isdir(os.path.join(media_directory, entry))
    ]


def main(device_driver_name: str) -> None:
    base_path = str(Path(heart.__file__).resolve().parents[2] / "drivers")
    code_path = os.path.join(base_path, device_driver_name)
    if not os.path.isdir(code_path):
        logger.error(
            "The path %s does not exist. This is where we expect the driver code to exist.",
            code_path,
        )
        sys.exit(1)

    ###
    # Load a bunch of env vars the driver declares
    ###
    config = _load_driver_config(os.path.join(code_path, DRIVER_SETTINGS_FILENAME))
    _ensure_driver_files(code_path)
    mount_points = _mount_points(MEDIA_DIRECTORY)

    ###
    # If the device is not a CIRCUIT_PY device yet, load the UF2 so that it is converted
    ###
    UF2_DESTINATION = os.path.join(MEDIA_DIRECTORY, config.device_boot_name)
    if os.path.isdir(UF2_DESTINATION):
        downloaded_file_path = download_file(config.uf2_url, config.uf2_checksum)
        copy_file(downloaded_file_path, UF2_DESTINATION)
        time.sleep(10)
    else:
        logger.info(
            "Skipping CircuitPython UF2 installation as no device is in boot mode currently"
        )

    ###
    # For all the CIRCUITPY devices, try to find whether this specific driver should be loaded onto them
    ###
    circuitpy_mounts = [
        mount_point
        for mount_point in mount_points
        if "CIRCUITPY" in os.path.basename(mount_point)
    ]
    if not circuitpy_mounts:
        logger.warning("No CIRCUITPY volumes found under %s.", MEDIA_DIRECTORY)

    for media_location in circuitpy_mounts:
        boot_out_path = os.path.join(media_location, "boot_out.txt")

        if os.path.exists(boot_out_path):
            try:
                board_id = _parse_board_id(boot_out_path)
            except ValueError as error:
                logger.warning("Unable to parse board ID: %s", error)
                continue

            if board_id not in config.valid_board_ids:
                logger.info(
                    "Skipping: The board ID %s is not in the list of valid board IDs: %s",
                    board_id,
                    config.valid_board_ids,
                )
                continue

            for file_name in DRIVER_FILES:
                copy_file(
                    os.path.join(code_path, file_name),
                    os.path.join(media_location, file_name),
                )

            load_driver_libs(
                libs=config.driver_libs,
                destination=os.path.join(os.path.join(media_location, "lib")),
            )
        else:
            logger.info("%s is missing, skipping...", boot_out_path)


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
    main(sys.argv[1])
