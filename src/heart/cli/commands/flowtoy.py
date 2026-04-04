"""Operator commands for FlowToy radio bridges."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Iterator

import serial.tools.list_ports
import typer
from heart_firmware_io import constants as firmware_constants
from heart_firmware_io import flowtoy as flowtoy_protocol
from heart_firmware_io.radio import FLOWTOY_PROTOCOL

from heart.peripheral.radio import (FlowToyPattern, SerialRadioDriver,
                                    SerialRadioMessage)
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

app = typer.Typer(help="Discover and control FlowToy radio bridges.")

FLOWTOY_DEVICE_NAME = "feather-flowtoy-bridge"
DEFAULT_DISCOVER_SECONDS = 5.0
DEFAULT_LISTEN_SECONDS = 30.0
DEFAULT_COMMAND_REPEAT_COUNT = 5
DEFAULT_COMMAND_INTERVAL_SECONDS = 0.35
DEFAULT_ACM_GLOB = "/dev/ttyACM*"
DEFAULT_USB_GLOB = "/dev/ttyUSB*"


@dataclass(frozen=True, slots=True)
class FlowToyBridge:
    """Bridge metadata required for operator actions."""

    port: str
    mode: str


def _candidate_ports() -> list[str]:
    """Return likely bridge ports with OS-reported devices preferred first."""

    detected_ports = [port.device for port in serial.tools.list_ports.comports()]
    fallback_ports = [
        str(path)
        for pattern in (DEFAULT_ACM_GLOB, DEFAULT_USB_GLOB)
        for path in sorted(Path("/").glob(pattern.lstrip("/")))
    ]
    ordered_ports = detected_ports + fallback_ports
    unique_ports: list[str] = []
    seen_ports: set[str] = set()
    for port in ordered_ports:
        if port in seen_ports:
            continue
        seen_ports.add(port)
        unique_ports.append(port)
    return unique_ports


def _detect_bridges(port: str | None = None) -> list[FlowToyBridge]:
    """Identify FlowToy bridges on one port or across likely serial devices."""

    bridges: list[FlowToyBridge] = []
    candidate_ports = [port] if port is not None else _candidate_ports()
    for candidate in candidate_ports:
        driver = SerialRadioDriver(port=candidate)
        try:
            identity = driver.identify()
        except Exception:
            logger.debug("FlowToy identify failed on %s", candidate, exc_info=True)
            continue
        if identity is None:
            continue
        if identity.get("protocol") != FLOWTOY_PROTOCOL:
            continue
        if identity.get("device_name") != FLOWTOY_DEVICE_NAME:
            continue
        bridges.append(
            FlowToyBridge(
                port=candidate,
                mode=str(identity.get("mode", "")),
            )
        )
    return bridges


def _require_bridges(port: str | None = None) -> list[FlowToyBridge]:
    bridges = _detect_bridges(port)
    if bridges:
        return bridges
    logger.error("No FlowToy bridges detected")
    raise typer.Exit(code=1)


def _resolve_transmit_bridge(port: str | None = None) -> FlowToyBridge:
    bridges = _require_bridges(port)
    for bridge in bridges:
        if bridge.mode == "transmit-receive":
            return bridge
    return bridges[0]


def _iter_flowtoy_messages(
    bridge: FlowToyBridge,
    *,
    duration_seconds: float,
) -> Iterator[tuple[SerialRadioMessage, dict[str, Any] | None]]:
    """Yield raw serial messages alongside any decoded FlowToy packet payload."""

    driver = SerialRadioDriver(port=bridge.port)
    for message in driver.read_messages(duration_seconds=duration_seconds):
        decoded = _decode_flowtoy_message(message)
        yield message, decoded


def _decode_flowtoy_message(message: SerialRadioMessage) -> dict[str, Any] | None:
    """Decode a shared radio message into a FlowToy sync payload when possible."""

    if message.event_type != firmware_constants.RADIO_PACKET or message.packet is None:
        return None
    if message.packet.protocol not in {None, FLOWTOY_PROTOCOL}:
        return None
    if message.packet.decoded:
        return dict(message.packet.decoded)
    return flowtoy_protocol.decode_if_matching(message.packet.payload)


def _render_packet_line(port: str, decoded: dict[str, Any], rssi_dbm: float | None) -> str:
    """Render a short operator-facing summary using 1-based FlowToy numbering."""

    user_page = int(decoded["page"]) + 1
    user_mode = int(decoded["mode"]) + 1
    return (
        f"{port} group_id={decoded['group_id']} "
        f"user_page={user_page} user_mode={user_mode} rssi={rssi_dbm}"
    )


def _build_user_pattern(*, group_id: int, page: int, mode: int) -> FlowToyPattern:
    """Build a shared FlowToy pattern using 1-based page and mode CLI values."""

    if page < 1 or mode < 1:
        raise typer.BadParameter("Page and mode must be 1-based user-facing values")
    return FlowToyPattern(
        group_id=group_id,
        page=page - 1,
        mode=mode - 1,
    )


def _send_pattern_command(
    bridge: FlowToyBridge,
    *,
    pattern: FlowToyPattern,
) -> None:
    """Send a shared FlowToy pattern command with a small reliability burst."""

    driver = SerialRadioDriver(port=bridge.port)
    command = pattern.to_serial_command()
    for _ in range(DEFAULT_COMMAND_REPEAT_COUNT):
        driver.send_raw_command(command)
        if DEFAULT_COMMAND_INTERVAL_SECONDS > 0:
            time.sleep(DEFAULT_COMMAND_INTERVAL_SECONDS)


@app.command("discover")
def discover_command(
    seconds: Annotated[
        float,
        typer.Option("--seconds", help="How long to watch for FlowToy packets."),
    ] = DEFAULT_DISCOVER_SECONDS,
    port: Annotated[
        str | None,
        typer.Option("--port", help="Specific bridge port to inspect."),
    ] = None,
) -> None:
    """Discover FlowToy group ids visible to the local radio bridge."""

    observed_groups: dict[int, str] = {}
    for bridge in _require_bridges(port):
        for message, decoded in _iter_flowtoy_messages(bridge, duration_seconds=seconds):
            if decoded is None:
                continue
            group_id = int(decoded["group_id"])
            observed_groups[group_id] = _render_packet_line(
                bridge.port,
                decoded,
                message.packet.rssi_dbm if message.packet is not None else None,
            )

    if not observed_groups:
        typer.echo("No local FlowToy groups observed.")
        return
    for group_id in sorted(observed_groups):
        typer.echo(observed_groups[group_id])


@app.command("listen")
def listen_command(
    seconds: Annotated[
        float,
        typer.Option("--seconds", help="How long to listen for packets."),
    ] = DEFAULT_LISTEN_SECONDS,
    port: Annotated[
        str | None,
        typer.Option("--port", help="Specific bridge port to inspect."),
    ] = None,
) -> None:
    """Stream decoded FlowToy packets."""

    for bridge in _require_bridges(port):
        for message, decoded in _iter_flowtoy_messages(bridge, duration_seconds=seconds):
            if decoded is None:
                continue
            typer.echo(
                _render_packet_line(
                    bridge.port,
                    decoded,
                    message.packet.rssi_dbm if message.packet is not None else None,
                )
            )


@app.command("set-mode")
def set_mode_command(
    group_id: Annotated[int, typer.Option("--group-id", help="Target FlowToy group id.")],
    page: Annotated[int, typer.Option("--page", help="User-facing page number.")],
    mode: Annotated[int, typer.Option("--mode", help="User-facing mode number.")],
    port: Annotated[
        str | None,
        typer.Option("--port", help="Specific transmit bridge port."),
    ] = None,
) -> None:
    """Send a FlowToy page and mode update."""

    bridge = _resolve_transmit_bridge(port)
    pattern = _build_user_pattern(group_id=group_id, page=page, mode=mode)
    _send_pattern_command(bridge, pattern=pattern)
    typer.echo(
        f"Sent {pattern.to_serial_command()} on {bridge.port} "
        f"(group_id={group_id}, user_page={page}, user_mode={mode})."
    )
