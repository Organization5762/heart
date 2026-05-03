"""Driver update configuration parsing."""

from dataclasses import dataclass
from pathlib import Path

import toml
from heart_device_manager.driver_update.exceptions import UpdateError
from heart_device_manager.driver_update.modes import UpdateMode
from heart_device_manager.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ArduinoConfig:
    board_manager_urls: list[str]
    core: str
    fqbn: str
    libraries: list[str]
    port_keywords: list[str]
    sketch_path: Path


@dataclass(frozen=True)
class DriverConfig:
    uf2_url: str
    uf2_checksum: str
    driver_libs: list[str]
    device_boot_name: str
    valid_board_ids: list[str]
    default_update_mode: UpdateMode
    arduino: ArduinoConfig | None


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


def _parse_update_mode(value: object) -> UpdateMode:
    if value is None:
        return UpdateMode.CIRCUITPYTHON
    if not isinstance(value, str):
        raise ValueError(
            f"Expected DEFAULT_UPDATE_MODE to be a string, got {value!r}"
        )
    try:
        return UpdateMode(value.strip().lower())
    except ValueError as error:
        supported = ", ".join(mode.value for mode in UpdateMode)
        raise ValueError(
            f"Expected DEFAULT_UPDATE_MODE to be one of {supported}, got {value!r}"
        ) from error


def _load_arduino_config(
    config: dict[str, object], *, settings_path: Path
) -> ArduinoConfig | None:
    if "ARDUINO_SKETCH_PATH" not in config:
        return None

    sketch_path = (
        settings_path.parent
        / _require_string(
            config["ARDUINO_SKETCH_PATH"], field_name="ARDUINO_SKETCH_PATH"
        )
    ).resolve()
    if not sketch_path.exists():
        raise ValueError(
            f"Expected ARDUINO_SKETCH_PATH to exist, got {sketch_path}"
        )

    port_keywords = _parse_csv(
        config.get("ARDUINO_PORT_KEYWORDS", ""),
        field_name="ARDUINO_PORT_KEYWORDS",
    )
    if not port_keywords:
        raise ValueError(
            "Expected ARDUINO_PORT_KEYWORDS to include at least one entry"
        )

    return ArduinoConfig(
        board_manager_urls=_parse_csv(
            config.get("ARDUINO_BOARD_MANAGER_URLS", ""),
            field_name="ARDUINO_BOARD_MANAGER_URLS",
        ),
        core=_require_string(config.get("ARDUINO_CORE"), field_name="ARDUINO_CORE"),
        fqbn=_require_string(config.get("ARDUINO_FQBN"), field_name="ARDUINO_FQBN"),
        libraries=_parse_csv(
            config.get("ARDUINO_LIBRARIES", ""),
            field_name="ARDUINO_LIBRARIES",
        ),
        port_keywords=port_keywords,
        sketch_path=sketch_path,
    )


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
        default_update_mode = _parse_update_mode(config.get("DEFAULT_UPDATE_MODE"))
        arduino_config = _load_arduino_config(config, settings_path=settings_path)
    except ValueError as error:
        message = f"Invalid driver settings in {settings_path}: {error}"
        logger.error(message)
        raise UpdateError(message) from error

    if default_update_mode == UpdateMode.ARDUINO and arduino_config is None:
        message = (
            f"Invalid driver settings in {settings_path}: "
            "DEFAULT_UPDATE_MODE is arduino but no Arduino sketch is configured"
        )
        logger.error(message)
        raise UpdateError(message)

    return DriverConfig(
        uf2_url=uf2_url,
        uf2_checksum=uf2_checksum,
        driver_libs=driver_libs,
        device_boot_name=device_boot_name,
        valid_board_ids=valid_board_ids,
        default_update_mode=default_update_mode,
        arduino=arduino_config,
    )
