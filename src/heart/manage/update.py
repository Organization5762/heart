import hashlib
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
    MEDIA_DIRECTORY = Path("/media/michael")
else:
    MEDIA_DIRECTORY = Path("/Volumes")

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


class UpdateError(Exception):
    """Raise when driver update preconditions or downloads fail."""


@dataclass(frozen=True)
class DriverConfig:
    uf2_url: str
    uf2_checksum: str
    driver_libs: list[str]
    device_boot_name: str
    valid_board_ids: list[str]


def load_driver_libs(libs: list[str], destination: Path) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    # Our local lib
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
    # Lib in this case just comes from the downloaded file, which is separate from the `destination` which is also lib
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
        # There are also .mpy files..
        mpy_source = lib_path / f"{lib}.mpy"
        if mpy_source.exists():
            copy_file(mpy_source, destination / f"{lib}.mpy")
        else:
            logger.warning("Skipping missing %s", mpy_source)


def _sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, checksum: str) -> Path:
    try:
        destination = Path("/tmp") / url.split("/")[-1]
        if destination.exists():
            existing_checksum = _sha256sum(destination)
            if existing_checksum != checksum:
                logger.warning(
                    "Removing %s; checksum %s did not match %s.",
                    destination,
                    existing_checksum,
                    checksum,
                )
                destination.unlink()

        if not destination.exists():
            logger.info("Starting download: %s", url)
            if Configuration.is_pi():
                subprocess.run(["wget", url, "-O", str(destination)], check=True)
            else:
                subprocess.run(
                    ["curl", "-fL", url, "-o", str(destination)], check=True
                )
            logger.info("Finished download: %s", destination)

        downloaded_checksum = _sha256sum(destination)
        logger.info("Checksum for %s: %s", destination, downloaded_checksum)
        if downloaded_checksum != checksum:
            message = (
                f"Checksum mismatch for {destination}. "
                f"Expected {checksum}, but got {downloaded_checksum}."
            )
            logger.error(message)
            raise UpdateError(message)
        logger.info("Checksum matches expectations.")
        return destination
    except subprocess.CalledProcessError:
        message = f"Failed to download {url}"
        logger.error(message)
        raise UpdateError(message) from None


def copy_file(source: Path, destination: Path) -> None:
    try:
        logger.info("Before copying: %s to %s", source, destination)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
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


def _load_driver_config(settings_path: Path) -> DriverConfig:
    try:
        config = toml.load(settings_path)
    except (FileNotFoundError, toml.TomlDecodeError) as error:
        message = f"Unable to read driver settings at {settings_path}: {error}"
        logger.error(message)
        raise UpdateError(message) from error

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
        message = (
            f"Missing keys in {settings_path}: {', '.join(missing)}"
        )
        logger.error(message)
        raise UpdateError(message)

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
        message = f"Invalid driver settings in {settings_path}: {error}"
        logger.error(message)
        raise UpdateError(message) from error

    return DriverConfig(
        uf2_url=uf2_url,
        uf2_checksum=uf2_checksum,
        driver_libs=driver_libs,
        device_boot_name=device_boot_name,
        valid_board_ids=valid_board_ids,
    )


def _parse_board_id(boot_out_path: Path) -> str:
    with boot_out_path.open("r") as file_handle:
        for line in file_handle:
            if "Board ID:" in line:
                return line.split("Board ID:")[1].strip()
    raise ValueError(f"Unable to find Board ID identifier in {boot_out_path}")


def _ensure_driver_files(driver_path: Path) -> None:
    missing = [
        name
        for name in DRIVER_FILES
        if not (driver_path / name).exists()
    ]
    if missing:
        message = f"Missing driver files in {driver_path}: {', '.join(missing)}"
        logger.error(message)
        raise UpdateError(message)


def _mount_points(media_directory: Path) -> list[Path]:
    if not media_directory.is_dir():
        message = (
            f"Expected media directory {media_directory} to exist before updates."
        )
        logger.error(message)
        raise UpdateError(message)

    return [
        entry for entry in media_directory.iterdir() if entry.is_dir()
    ]


def _driver_base_path() -> Path:
    return Path(heart.__file__).resolve().parents[2] / "drivers"


def _get_driver_path(device_driver_name: str) -> Path:
    code_path = _driver_base_path() / device_driver_name
    if not code_path.is_dir():
        message = (
            "The path "
            f"{code_path} does not exist. This is where we expect the driver code to exist."
        )
        logger.error(message)
        raise UpdateError(message)
    return code_path


def _install_uf2_if_available(config: DriverConfig) -> None:
    uf2_destination = MEDIA_DIRECTORY / config.device_boot_name
    if uf2_destination.is_dir():
        downloaded_file_path = download_file(config.uf2_url, config.uf2_checksum)
        copy_file(downloaded_file_path, uf2_destination)
        time.sleep(10)
    else:
        logger.info(
            "Skipping CircuitPython UF2 installation as no device is in boot mode currently"
        )


def _circuitpy_mounts(mount_points: list[Path]) -> list[Path]:
    circuitpy_mounts = [
        mount_point
        for mount_point in mount_points
        if "CIRCUITPY" in mount_point.name
    ]
    if not circuitpy_mounts:
        logger.warning("No CIRCUITPY volumes found under %s.", MEDIA_DIRECTORY)
    return circuitpy_mounts


def _update_circuitpy_mount(
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


def main(device_driver_name: str) -> None:
    code_path = _get_driver_path(device_driver_name)
    config = _load_driver_config(code_path / DRIVER_SETTINGS_FILENAME)
    _ensure_driver_files(code_path)
    mount_points = _mount_points(MEDIA_DIRECTORY)
    _install_uf2_if_available(config)
    for media_location in _circuitpy_mounts(mount_points):
        _update_circuitpy_mount(media_location, config, code_path)


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
