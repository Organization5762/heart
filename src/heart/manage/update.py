import argparse
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

DEFAULT_MEDIA_DIRECTORY = Path(
    "/media/michael" if Configuration.is_pi() else "/Volumes"
)

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


@dataclass(frozen=True)
class UpdateOptions:
    media_directory: Path
    skip_uf2: bool
    skip_libs: bool
    dry_run: bool


def load_driver_libs(
    libs: list[str], destination: Path, *, dry_run: bool = False
) -> None:
    if dry_run:
        logger.info("Dry run: would reset %s and sync driver libs.", destination)
        return

    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    copy_file(
        Path(firmware_io.__file__).parent,
        destination / Path(*firmware_io.__package__.split(".")),
        dry_run=dry_run,
    )

    if not libs:
        logger.info("Skipping driver libs because no libs were requested.")
        return

    logger.info("Loading driver libs: %s", libs)
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
        logger.info("Skipping unzip for %s because %s exists.", zip_location, lib_path)

    for lib in libs:
        copy_file(lib_path / lib, destination / lib)
        # There are also .mpy files..
        mpy_source = lib_path / f"{lib}.mpy"
        if mpy_source.exists():
            copy_file(mpy_source, destination / f"{lib}.mpy")
        else:
            logger.info("Skipping missing %s", mpy_source)


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
                subprocess.run(["curl", "-fL", url, "-o", str(destination)], check=True)
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
            raise SystemExit(1)
        logger.info("Checksum matches expectations.")
        return destination
    except subprocess.CalledProcessError:
        logger.error("Failed to download %s", url)
        raise SystemExit(1)


def copy_file(source: Path, destination: Path, *, dry_run: bool = False) -> None:
    if dry_run:
        logger.info("Dry run: would copy %s to %s", source, destination)
        return

    try:
        logger.info("Copying %s to %s", source, destination)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
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
        raise SystemExit(1)

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
        logger.error("Missing keys in %s: %s", settings_path, ", ".join(missing))
        raise SystemExit(1)

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
        raise SystemExit(1)

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
        name for name in DRIVER_FILES if not (driver_path / name).exists()
    ]
    if missing:
        logger.error("Missing driver files in %s: %s", driver_path, ", ".join(missing))
        raise SystemExit(1)


def _mount_points(media_directory: Path) -> list[Path]:
    if not media_directory.is_dir():
        logger.error(
            "Expected media directory %s to exist before updates.", media_directory
        )
        raise SystemExit(1)

    return [
        entry for entry in media_directory.iterdir() if entry.is_dir()
    ]


def main(device_driver_name: str, options: UpdateOptions) -> None:
    base_path = Path(heart.__file__).resolve().parents[2] / "drivers"
    code_path = base_path / device_driver_name
    if not code_path.is_dir():
        logger.error(
            "The path %s does not exist. This is where we expect the driver code to exist.",
            code_path,
        )
        raise SystemExit(1)

    ###
    # Load a bunch of env vars the driver declares
    ###
    config = _load_driver_config(str(code_path / DRIVER_SETTINGS_FILENAME))
    _ensure_driver_files(code_path)
    mount_points = _mount_points(options.media_directory)

    ###
    # If the device is not a CIRCUIT_PY device yet, load the UF2 so that it is converted
    ###
    if options.skip_uf2:
        logger.info("Skipping CircuitPython UF2 installation due to --skip-uf2.")
    else:
        uf2_destination = options.media_directory / config.device_boot_name
        if uf2_destination.is_dir():
            if options.dry_run:
                logger.info(
                    "Dry run: would install UF2 %s to %s.",
                    config.uf2_url,
                    uf2_destination,
                )
            else:
                downloaded_file_path = download_file(
                    config.uf2_url, config.uf2_checksum
                )
                copy_file(downloaded_file_path, uf2_destination)
                time.sleep(10)
        else:
            logger.info(
                "Skipping CircuitPython UF2 installation as no device is in boot mode currently."
            )

    ###
    # For all the CIRCUITPY devices, try to find whether this specific driver should be loaded onto them
    ###
    circuitpy_mounts = [
        mount_point
        for mount_point in mount_points
        if "CIRCUITPY" in mount_point.name
    ]
    if not circuitpy_mounts:
        logger.info("No CIRCUITPY volumes found under %s.", options.media_directory)

    for media_location in circuitpy_mounts:
        boot_out_path = media_location / "boot_out.txt"

        if boot_out_path.exists():
            try:
                board_id = _parse_board_id(boot_out_path)
            except ValueError as error:
                logger.warning("%s", error)
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
                    code_path / file_name,
                    media_location / file_name,
                    dry_run=options.dry_run,
                )

            if options.skip_libs:
                logger.info(
                    "Skipping driver libs for %s due to --skip-libs.", media_location
                )
            else:
                load_driver_libs(
                    libs=config.driver_libs,
                    destination=media_location / "lib",
                    dry_run=options.dry_run,
                )
        else:
            logger.info("%s is missing, skipping...", boot_out_path)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install or update CircuitPython driver files on mounted devices."
    )
    parser.add_argument(
        "device_driver_name",
        help="Folder name under drivers/ that contains the CircuitPython assets.",
    )
    parser.add_argument(
        "--media-dir",
        default=str(DEFAULT_MEDIA_DIRECTORY),
        help="Override the media directory used for mounted volumes.",
    )
    parser.add_argument(
        "--skip-uf2",
        action="store_true",
        help="Skip UF2 installation even if a device is in boot mode.",
    )
    parser.add_argument(
        "--skip-libs",
        action="store_true",
        help="Skip syncing the bundled driver libraries.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log intended operations without modifying devices or downloads.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    options = UpdateOptions(
        media_directory=Path(args.media_dir),
        skip_uf2=args.skip_uf2,
        skip_libs=args.skip_libs,
        dry_run=args.dry_run,
    )
    main(args.device_driver_name, options)
