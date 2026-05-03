"""Native Arduino firmware update helpers."""

from __future__ import annotations

import os
import shutil
import subprocess

import serial.tools.list_ports
from heart_device_manager.driver_update.configuration import (ArduinoConfig,
                                                              DriverConfig)
from heart_device_manager.driver_update.exceptions import UpdateError
from heart_device_manager.logging import get_logger

logger = get_logger(__name__)

ARDUINO_CLI_BIN_ENV_VAR = "HEART_ARDUINO_CLI_BIN"
ARDUINO_PORT_ENV_VAR = "HEART_ARDUINO_PORT"
DEFAULT_ARDUINO_CLI_BIN = "arduino-cli"
ARDUINO_UPLOAD_VERIFY_FLAG = "--verify"


def update_arduino_sketch(config: DriverConfig) -> None:
    """Compile and upload the configured Arduino sketch."""

    arduino_config = config.arduino
    if arduino_config is None:
        message = "Arduino update requested, but no Arduino sketch is configured"
        logger.error(message)
        raise UpdateError(message)

    cli_binary = _resolve_arduino_cli_binary()
    command_prefix = _arduino_command_prefix(
        cli_binary, arduino_config.board_manager_urls
    )
    _install_arduino_core(command_prefix, arduino_config)
    _install_arduino_libraries(command_prefix, arduino_config)
    _compile_sketch(command_prefix, arduino_config)
    port = resolve_arduino_port(arduino_config)
    _upload_sketch(command_prefix, arduino_config, port)


def resolve_arduino_port(config: ArduinoConfig) -> str:
    """Resolve the serial port used for the configured Arduino board."""

    overridden_port = os.getenv(ARDUINO_PORT_ENV_VAR, "").strip()
    if overridden_port:
        logger.info(
            "Using Arduino upload port from %s: %s",
            ARDUINO_PORT_ENV_VAR,
            overridden_port,
        )
        return overridden_port

    scored_ports: list[tuple[int, str]] = []
    for port in serial.tools.list_ports.comports():
        score = _port_match_score(port=port, keywords=config.port_keywords)
        if score > 0:
            scored_ports.append((score, str(port.device)))

    if not scored_ports:
        message = (
            "Unable to find an Arduino upload port matching "
            f"{config.port_keywords!r}. Set {ARDUINO_PORT_ENV_VAR} to override."
        )
        logger.error(message)
        raise UpdateError(message)

    scored_ports.sort(reverse=True)
    highest_score = scored_ports[0][0]
    best_ports = [
        device for score, device in scored_ports if score == highest_score
    ]
    if len(best_ports) != 1:
        message = (
            "Multiple Arduino upload ports matched the configured keywords: "
            f"{best_ports}. Set {ARDUINO_PORT_ENV_VAR} to choose one explicitly."
        )
        logger.error(message)
        raise UpdateError(message)

    selected_port = best_ports[0]
    logger.info("Resolved Arduino upload port %s", selected_port)
    return selected_port


def _resolve_arduino_cli_binary() -> str:
    configured_binary = os.getenv(ARDUINO_CLI_BIN_ENV_VAR, DEFAULT_ARDUINO_CLI_BIN)
    cli_binary = configured_binary.strip() or DEFAULT_ARDUINO_CLI_BIN
    if shutil.which(cli_binary) is None:
        message = (
            f"Unable to find {cli_binary!r}. Install arduino-cli or set "
            f"{ARDUINO_CLI_BIN_ENV_VAR} to the binary path."
        )
        logger.error(message)
        raise UpdateError(message)
    return cli_binary


def _arduino_command_prefix(
    cli_binary: str, board_manager_urls: list[str]
) -> list[str]:
    command = [cli_binary]
    if board_manager_urls:
        command.extend(["--additional-urls", ",".join(board_manager_urls)])
    return command


def _install_arduino_core(
    command_prefix: list[str], config: ArduinoConfig
) -> None:
    logger.info("Installing Arduino core %s", config.core)
    _run_arduino_cli(command_prefix + ["core", "update-index"])
    _run_arduino_cli(command_prefix + ["core", "install", config.core])


def _install_arduino_libraries(
    command_prefix: list[str], config: ArduinoConfig
) -> None:
    for library in config.libraries:
        logger.info("Installing Arduino library %s", library)
        _run_arduino_cli(command_prefix + ["lib", "install", library])


def _compile_sketch(command_prefix: list[str], config: ArduinoConfig) -> None:
    logger.info("Compiling Arduino sketch %s", config.sketch_path)
    _run_arduino_cli(
        command_prefix
        + ["compile", "--fqbn", config.fqbn, str(config.sketch_path)]
    )


def _upload_sketch(
    command_prefix: list[str], config: ArduinoConfig, port: str
) -> None:
    logger.info("Uploading Arduino sketch %s to %s", config.sketch_path, port)
    _run_arduino_cli(
        command_prefix
        + [
            "upload",
            "--fqbn",
            config.fqbn,
            "--port",
            port,
            ARDUINO_UPLOAD_VERIFY_FLAG,
            str(config.sketch_path),
        ]
    )


def _run_arduino_cli(command: list[str]) -> None:
    completed_process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed_process.returncode == 0:
        return

    stderr = completed_process.stderr.strip()
    stdout = completed_process.stdout.strip()
    command_display = " ".join(command)
    message = (
        f"Arduino CLI command failed: {command_display}\n"
        f"stdout: {stdout or '<empty>'}\n"
        f"stderr: {stderr or '<empty>'}"
    )
    logger.error(message)
    raise UpdateError(message)


def _port_match_score(*, port: object, keywords: list[str]) -> int:
    searchable_fields = [
        getattr(port, "device", ""),
        getattr(port, "description", ""),
        getattr(port, "manufacturer", ""),
        getattr(port, "product", ""),
        getattr(port, "hwid", ""),
    ]
    searchable_text = " ".join(str(value).lower() for value in searchable_fields)
    return sum(1 for keyword in keywords if keyword.lower() in searchable_text)
