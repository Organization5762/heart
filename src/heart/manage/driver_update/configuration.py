"""Driver update configuration parsing."""

from dataclasses import dataclass
from pathlib import Path

import toml

from heart.manage.driver_update.exceptions import UpdateError
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DriverConfig:
    uf2_url: str
    uf2_checksum: str
    driver_libs: list[str]
    device_boot_name: str
    valid_board_ids: list[str]


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


def load_driver_config(settings_path: Path) -> DriverConfig:
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
        message = f"Missing keys in {settings_path}: {', '.join(missing)}"
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
