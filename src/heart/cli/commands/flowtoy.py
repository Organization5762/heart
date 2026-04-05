"""Operator commands for FlowToy radio bridges."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Iterator

import serial.tools.list_ports
import typer
from heart_firmware_io import constants as firmware_constants

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
FLOWTOY_PROTOCOL = "flowtoy"
DEFAULT_GROUP_OBSERVE_SECONDS = 5.0
DEFAULT_BRIGHTNESS_SCAN_STEP = 10
DEFAULT_BRIGHTNESS_SCAN_DELAY_SECONDS = 1.0
FLOWTOY_LFO_ACTIVE_BIT = 1 << 0
FLOWTOY_HUE_ACTIVE_BIT = 1 << 1
FLOWTOY_SATURATION_ACTIVE_BIT = 1 << 2
FLOWTOY_BRIGHTNESS_ACTIVE_BIT = 1 << 3
FLOWTOY_SPEED_ACTIVE_BIT = 1 << 4
FLOWTOY_DENSITY_ACTIVE_BIT = 1 << 5


def _active_bit_from_name(name: str) -> int:
    """Return the FlowToy active bit for a CLI override field name."""

    return {
        "lfo": FLOWTOY_LFO_ACTIVE_BIT,
        "hue_offset": FLOWTOY_HUE_ACTIVE_BIT,
        "saturation": FLOWTOY_SATURATION_ACTIVE_BIT,
        "brightness": FLOWTOY_BRIGHTNESS_ACTIVE_BIT,
        "speed": FLOWTOY_SPEED_ACTIVE_BIT,
        "density": FLOWTOY_DENSITY_ACTIVE_BIT,
    }[name]


@dataclass(frozen=True, slots=True)
class FlowToyBridge:
    """Bridge metadata required for operator actions."""

    port: str
    mode: str


def _decode_flowtoy_payload(payload: bytes) -> dict[str, Any] | None:
    """Decode FlowToy payload bytes on demand."""

    try:
        from heart_firmware_io import flowtoy as flowtoy_protocol
    except ImportError as exc:
        logger.error(
            "FlowToy firmware helpers are unavailable; reinstall heart-firmware-io "
            "so the flowtoy module is present"
        )
        raise typer.Exit(code=1) from exc
    return flowtoy_protocol.decode_if_matching(payload)


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
    return _decode_flowtoy_payload(message.packet.payload)


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


def _build_pattern_from_user_values(
    *,
    group_id: int,
    page: int,
    mode: int,
    actives: int | None = None,
    hue_offset: int | None = None,
    saturation: int | None = None,
    brightness: int | None = None,
    speed: int | None = None,
    density: int | None = None,
) -> FlowToyPattern:
    """Build a direct FlowToy pattern from explicit user-facing values."""

    pattern = _build_user_pattern(group_id=group_id, page=page, mode=mode)
    if all(
        value is None
        for value in (
            actives,
            hue_offset,
            saturation,
            brightness,
            speed,
            density,
        )
    ):
        return pattern

    resolved_actives = int(actives or 0)
    for name, value in (
        ("hue_offset", hue_offset),
        ("saturation", saturation),
        ("brightness", brightness),
        ("speed", speed),
        ("density", density),
    ):
        if value is not None:
            resolved_actives |= _active_bit_from_name(name)
    return FlowToyPattern(
        group_id=pattern.group_id,
        page=pattern.page,
        mode=pattern.mode,
        actives=resolved_actives,
        hue_offset=int(hue_offset or 0),
        saturation=int(saturation or 0),
        brightness=int(brightness or 0),
        speed=int(speed or 0),
        density=int(density or 0),
    )


def _build_pattern_from_decoded(
    *,
    decoded: dict[str, Any],
    group_id: int,
    page: int | None = None,
    mode: int | None = None,
    actives: int | None = None,
    hue_offset: int | None = None,
    saturation: int | None = None,
    brightness: int | None = None,
    speed: int | None = None,
    density: int | None = None,
) -> FlowToyPattern:
    """Reuse observed sync-packet state while applying CLI overrides."""

    global_settings = decoded.get("global")
    if not isinstance(global_settings, dict):
        global_settings = {}
    active_flags = decoded.get("active_flags")
    if not isinstance(active_flags, dict):
        active_flags = {}
    lfo_values = decoded.get("lfo")
    if not isinstance(lfo_values, list):
        lfo_values = []

    resolved_actives = 0
    if bool(active_flags.get("lfo")):
        resolved_actives |= FLOWTOY_LFO_ACTIVE_BIT
    if bool(active_flags.get("hue")):
        resolved_actives |= FLOWTOY_HUE_ACTIVE_BIT
    if bool(active_flags.get("saturation")):
        resolved_actives |= FLOWTOY_SATURATION_ACTIVE_BIT
    if bool(active_flags.get("brightness")):
        resolved_actives |= FLOWTOY_BRIGHTNESS_ACTIVE_BIT
    if bool(active_flags.get("speed")):
        resolved_actives |= FLOWTOY_SPEED_ACTIVE_BIT
    if bool(active_flags.get("density")):
        resolved_actives |= FLOWTOY_DENSITY_ACTIVE_BIT
    for name, value in (
        ("hue_offset", hue_offset),
        ("saturation", saturation),
        ("brightness", brightness),
        ("speed", speed),
        ("density", density),
    ):
        if value is not None:
            resolved_actives |= _active_bit_from_name(name)
    if actives is not None:
        resolved_actives = int(actives)

    resolved_page = int(decoded["page"]) if page is None else page - 1
    resolved_mode = int(decoded["mode"]) if mode is None else mode - 1
    if resolved_page < 0 or resolved_mode < 0:
        raise typer.BadParameter("Page and mode must be 1-based user-facing values")

    return FlowToyPattern(
        group_id=group_id,
        page=resolved_page,
        mode=resolved_mode,
        actives=resolved_actives,
        hue_offset=(
            int(global_settings.get("hue", 0))
            if hue_offset is None
            else int(hue_offset)
        ),
        saturation=(
            int(global_settings.get("saturation", 0))
            if saturation is None
            else int(saturation)
        ),
        brightness=(
            int(global_settings.get("brightness", 0))
            if brightness is None
            else int(brightness)
        ),
        speed=(
            int(global_settings.get("speed", 0))
            if speed is None
            else int(speed)
        ),
        density=(
            int(global_settings.get("density", 0))
            if density is None
            else int(density)
        ),
        lfo1=int(lfo_values[0]) if len(lfo_values) > 0 else 0,
        lfo2=int(lfo_values[1]) if len(lfo_values) > 1 else 0,
        lfo3=int(lfo_values[2]) if len(lfo_values) > 2 else 0,
        lfo4=int(lfo_values[3]) if len(lfo_values) > 3 else 0,
    )


def _observe_group_state(
    bridge: FlowToyBridge,
    *,
    group_id: int,
    seconds: float,
    required: bool = True,
) -> dict[str, Any] | None:
    """Return the most recent decoded packet for a specific FlowToy group."""

    latest_decoded: dict[str, Any] | None = None
    for _message, decoded in _iter_flowtoy_messages(bridge, duration_seconds=seconds):
        if decoded is None:
            continue
        if int(decoded.get("group_id", -1)) != group_id:
            continue
        latest_decoded = decoded

    if latest_decoded is not None:
        return latest_decoded

    if not required:
        return None

    logger.error(
        "No decoded FlowToy sync packets observed for group_id=%s in %.1f seconds",
        group_id,
        seconds,
    )
    raise typer.Exit(code=1)


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
    page: Annotated[
        int | None,
        typer.Option("--page", help="User-facing page number. Defaults to the observed page."),
    ] = None,
    mode: Annotated[
        int | None,
        typer.Option("--mode", help="User-facing mode number. Defaults to the observed mode."),
    ] = None,
    actives: Annotated[
        int | None,
        typer.Option("--actives", min=0, max=255, help="Override the raw FlowToy actives bitfield."),
    ] = None,
    hue_offset: Annotated[
        int | None,
        typer.Option("--hue-offset", min=0, max=255, help="Override sync-packet hue offset."),
    ] = None,
    saturation: Annotated[
        int | None,
        typer.Option("--saturation", min=0, max=255, help="Override sync-packet saturation."),
    ] = None,
    brightness: Annotated[
        int | None,
        typer.Option("--brightness", min=0, max=255, help="Override sync-packet brightness."),
    ] = None,
    speed: Annotated[
        int | None,
        typer.Option("--speed", min=0, max=255, help="Override sync-packet speed."),
    ] = None,
    density: Annotated[
        int | None,
        typer.Option("--density", min=0, max=255, help="Override sync-packet density."),
    ] = None,
    brightness_scan_start: Annotated[
        int | None,
        typer.Option("--brightness-scan-start", min=0, max=255, help="Start brightness for a scan."),
    ] = None,
    brightness_scan_end: Annotated[
        int | None,
        typer.Option("--brightness-scan-end", min=0, max=255, help="End brightness for a scan."),
    ] = None,
    brightness_scan_step: Annotated[
        int,
        typer.Option("--brightness-scan-step", min=1, help="Step size for brightness scan."),
    ] = DEFAULT_BRIGHTNESS_SCAN_STEP,
    brightness_scan_delay: Annotated[
        float,
        typer.Option("--brightness-scan-delay", min=0.0, help="Delay between brightness scan steps."),
    ] = DEFAULT_BRIGHTNESS_SCAN_DELAY_SECONDS,
    observe_seconds: Annotated[
        float,
        typer.Option("--observe-seconds", min=0.1, help="How long to observe the group before reusing its sync state."),
    ] = DEFAULT_GROUP_OBSERVE_SECONDS,
    port: Annotated[
        str | None,
        typer.Option("--port", help="Specific transmit bridge port."),
    ] = None,
) -> None:
    """Send a FlowToy page and mode update."""

    bridge = _resolve_transmit_bridge(port)
    brightness_scan_requested = (
        brightness_scan_start is not None or brightness_scan_end is not None
    )
    if brightness_scan_requested and (
        brightness_scan_start is None or brightness_scan_end is None
    ):
        raise typer.BadParameter(
            "Brightness scans require both --brightness-scan-start and --brightness-scan-end"
        )
    if brightness is not None and brightness_scan_requested:
        raise typer.BadParameter(
            "Use either --brightness or a brightness scan, not both"
        )

    has_field_overrides = any(
        value is not None
        for value in (actives, hue_offset, saturation, brightness, speed, density)
    )
    if page is not None and mode is not None and not has_field_overrides and not brightness_scan_requested:
        pattern = _build_user_pattern(group_id=group_id, page=page, mode=mode)
        _send_pattern_command(bridge, pattern=pattern)
        typer.echo(
            f"Sent {pattern.to_serial_command()} on {bridge.port} "
            f"(group_id={group_id}, user_page={page}, user_mode={mode})."
        )
        return

    decoded: dict[str, Any] | None = None
    if page is None or mode is None:
        decoded = _observe_group_state(
            bridge,
            group_id=group_id,
            seconds=observe_seconds,
        )
    else:
        decoded = _observe_group_state(
            bridge,
            group_id=group_id,
            seconds=observe_seconds,
            required=False,
        )

    if brightness_scan_requested:
        assert brightness_scan_start is not None
        assert brightness_scan_end is not None
        if brightness_scan_start <= brightness_scan_end:
            brightness_values = range(
                brightness_scan_start,
                brightness_scan_end + 1,
                brightness_scan_step,
            )
        else:
            brightness_values = range(
                brightness_scan_start,
                brightness_scan_end - 1,
                -brightness_scan_step,
            )

        for brightness_value in brightness_values:
            pattern = (
                _build_pattern_from_decoded(
                    decoded=decoded,
                    group_id=group_id,
                    page=page,
                    mode=mode,
                    actives=actives,
                    hue_offset=hue_offset,
                    saturation=saturation,
                    brightness=brightness_value,
                    speed=speed,
                    density=density,
                )
                if decoded is not None
                else _build_pattern_from_user_values(
                    group_id=group_id,
                    page=page,
                    mode=mode,
                    actives=actives,
                    hue_offset=hue_offset,
                    saturation=saturation,
                    brightness=brightness_value,
                    speed=speed,
                    density=density,
                )
            )
            _send_pattern_command(bridge, pattern=pattern)
            typer.echo(
                f"Sent {pattern.to_serial_command()} on {bridge.port} "
                f"(group_id={group_id}, brightness={brightness_value})."
            )
            if brightness_scan_delay > 0:
                time.sleep(brightness_scan_delay)
        return

    pattern = (
        _build_pattern_from_decoded(
            decoded=decoded,
            group_id=group_id,
            page=page,
            mode=mode,
            actives=actives,
            hue_offset=hue_offset,
            saturation=saturation,
            brightness=brightness,
            speed=speed,
            density=density,
        )
        if decoded is not None
        else _build_pattern_from_user_values(
            group_id=group_id,
            page=page,
            mode=mode,
            actives=actives,
            hue_offset=hue_offset,
            saturation=saturation,
            brightness=brightness,
            speed=speed,
            density=density,
        )
    )
    _send_pattern_command(bridge, pattern=pattern)
    typer.echo(
        f"Sent {pattern.to_serial_command()} on {bridge.port} "
        f"(group_id={group_id}, user_page={pattern.page + 1}, "
        f"user_mode={pattern.mode + 1}, actives={pattern.actives}, "
        f"hue_offset={pattern.hue_offset}, saturation={pattern.saturation}, "
        f"brightness={pattern.brightness}, speed={pattern.speed}, "
        f"density={pattern.density})."
    )
