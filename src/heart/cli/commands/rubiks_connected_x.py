"""Operator commands for Rubik's Connected X BLE discovery and inspection."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from heart.peripheral.rubiks_connected_x import (
    DEFAULT_MONITOR_SECONDS,
    DEFAULT_SCAN_TIMEOUT_SECONDS,
    DEFAULT_STATE_SYNC_TIMEOUT_SECONDS,
    RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR,
    RUBIKS_CONNECTED_X_BASELINE_CAPTURE_GESTURE,
    RUBIKS_CONNECTED_X_FACE_ORDER,
    RubiksConnectedXNotification,
    discover_rubiks_connected_x_candidates,
    inspect_rubiks_connected_x_services,
    load_rubiks_connected_x_baseline_facelets,
    monitor_rubiks_connected_x_notifications,
    render_candidate_line,
    render_notification_line,
    request_rubiks_connected_x_state,
    resolve_rubiks_connected_x_candidate,
    rubiks_connected_x_face_slice,
    rubiks_connected_x_baseline_path,
    save_rubiks_connected_x_baseline_facelets,
    serialize_rubiks_connected_x_notification,
    summarize_rubiks_connected_x_notifications,
)
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

app = typer.Typer(help="Discover and inspect Rubik's Connected X BLE cubes.")
DEFAULT_CALIBRATION_SECONDS = 3.0
DEFAULT_CALIBRATION_WARMUP_SECONDS = 6.0
DEFAULT_CALIBRATION_OUTPUT_PATH = Path("rubiks_connected_x_calibration.json")
DEFAULT_CALIBRATION_MOVES = ("U", "U'", "R", "R'", "F", "F'")
DEFAULT_BASELINE_OUTPUT_PATH = rubiks_connected_x_baseline_path()


@app.command("scan")
def scan_command(
    seconds: Annotated[
        float,
        typer.Option("--seconds", help="How long to scan for BLE advertisements."),
    ] = DEFAULT_SCAN_TIMEOUT_SECONDS,
    include_all: Annotated[
        bool,
        typer.Option(
            "--all/--candidates-only",
            help="Show every BLE device instead of only likely cube candidates.",
        ),
    ] = False,
) -> None:
    """Scan nearby BLE advertisements and list likely cube candidates."""

    try:
        candidates = asyncio.run(
            discover_rubiks_connected_x_candidates(
                timeout_seconds=seconds,
                include_all=include_all,
            )
        )
    except Exception:
        logger.exception("Rubik's Connected X scan failed.")
        raise typer.Exit(code=1)

    if not candidates:
        typer.echo("No Rubik's Connected X candidates found.")
        typer.echo(
            "Wake the cube by picking it up without twisting it so the LED flashes for 2-3 seconds, then scan again."
        )
        return

    for candidate in candidates:
        typer.echo(render_candidate_line(candidate))
    typer.echo("")
    typer.echo(
        f"Export {RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR}=<address> to reuse the chosen device in the runtime."
    )


@app.command("inspect")
def inspect_command(
    address: Annotated[
        str | None,
        typer.Option("--address", help="Specific BLE address to inspect."),
    ] = None,
    seconds: Annotated[
        float,
        typer.Option("--seconds", help="How long to scan when auto-selecting a cube."),
    ] = DEFAULT_SCAN_TIMEOUT_SECONDS,
) -> None:
    """Connect to one device and print its GATT services and characteristics."""

    try:
        candidate = asyncio.run(
            resolve_rubiks_connected_x_candidate(
                address=address,
                timeout_seconds=seconds,
            )
        )
        services = asyncio.run(inspect_rubiks_connected_x_services(candidate.address))
    except Exception:
        logger.exception("Rubik's Connected X GATT inspection failed.")
        raise typer.Exit(code=1)

    typer.echo(render_candidate_line(candidate))
    for service in services:
        typer.echo(f"SERVICE {service.uuid} {service.description}")
        for characteristic in service.characteristics:
            typer.echo(
                f"  CHAR {characteristic.uuid} props={list(characteristic.properties)} "
                f"description={characteristic.description!r}"
            )


@app.command("monitor")
def monitor_command(
    address: Annotated[
        str | None,
        typer.Option("--address", help="Specific BLE address to monitor."),
    ] = None,
    seconds: Annotated[
        float,
        typer.Option("--seconds", help="How long to collect notifications."),
    ] = DEFAULT_MONITOR_SECONDS,
    characteristic: Annotated[
        list[str] | None,
        typer.Option(
            "--characteristic",
            help="Optional characteristic UUID filter; can be repeated.",
        ),
    ] = None,
    scan_seconds: Annotated[
        float,
        typer.Option(
            "--scan-seconds",
            help="How long to scan when auto-selecting a cube.",
        ),
    ] = DEFAULT_SCAN_TIMEOUT_SECONDS,
) -> None:
    """Subscribe to raw notify characteristics and print observed payloads."""

    try:
        candidate = asyncio.run(
            resolve_rubiks_connected_x_candidate(
                address=address,
                timeout_seconds=scan_seconds,
            )
        )
        typer.echo(f"Monitoring {candidate.address} for {seconds:.1f}s.")
        notifications = asyncio.run(
            monitor_rubiks_connected_x_notifications(
                address=candidate.address,
                seconds=seconds,
                characteristic_uuids=characteristic,
                timeout_seconds=scan_seconds,
                on_notification=lambda notification: typer.echo(
                    render_notification_line(notification)
                ),
            )
        )
    except Exception:
        logger.exception("Rubik's Connected X notification monitor failed.")
        raise typer.Exit(code=1)

    if not notifications:
        typer.echo("No notifications captured.")
        typer.echo(
            "Twist one face at a time while monitoring so we can see which characteristics change."
        )


def _render_face_grid(facelets: str) -> str:
    rows = [facelets[index : index + 3] for index in range(0, 9, 3)]
    return "\n".join(rows)


def _render_state_summary(facelets: str) -> str:
    sections = []
    for face in RUBIKS_CONNECTED_X_FACE_ORDER:
        face_slice = rubiks_connected_x_face_slice(facelets, face)
        sections.append(f"{face}\n{_render_face_grid(face_slice)}")
    return "\n\n".join(sections)


@app.command("state")
def state_command(
    address: Annotated[
        str | None,
        typer.Option("--address", help="Specific BLE address to request state from."),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="How long to wait for a full state-sync response.",
        ),
    ] = DEFAULT_STATE_SYNC_TIMEOUT_SECONDS,
    scan_seconds: Annotated[
        float,
        typer.Option(
            "--scan-seconds",
            help="How long to scan when auto-selecting a cube.",
        ),
    ] = DEFAULT_SCAN_TIMEOUT_SECONDS,
) -> None:
    """Request one full cube-state sync and print the parsed URFDLB faces."""

    try:
        candidate = asyncio.run(
            resolve_rubiks_connected_x_candidate(
                address=address,
                timeout_seconds=scan_seconds,
            )
        )
        notification = asyncio.run(
            request_rubiks_connected_x_state(
                address=candidate.address,
                timeout_seconds=timeout,
            )
        )
    except Exception:
        logger.exception("Rubik's Connected X state request failed.")
        raise typer.Exit(code=1)

    if notification is None or notification.parsed_message is None:
        typer.echo("No full state-sync frame received.")
        typer.echo(
            "Wake the cube, keep it still for a moment, and try again while the cube is nearby."
        )
        raise typer.Exit(code=1)

    typer.echo(render_candidate_line(candidate))
    typer.echo(render_notification_line(notification))
    typer.echo("")
    typer.echo("Parsed URFDLB faces:")
    typer.echo(_render_state_summary(notification.parsed_message.facelets or ""))


@app.command("capture-baseline")
def capture_baseline_command(
    address: Annotated[
        str | None,
        typer.Option("--address", help="Specific BLE address to request state from."),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help="Where to write the 54-character facelet baseline.",
        ),
    ] = DEFAULT_BASELINE_OUTPUT_PATH,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="How long to wait for a full state-sync response.",
        ),
    ] = DEFAULT_STATE_SYNC_TIMEOUT_SECONDS,
    scan_seconds: Annotated[
        float,
        typer.Option(
            "--scan-seconds",
            help="How long to scan when auto-selecting a cube.",
        ),
    ] = DEFAULT_SCAN_TIMEOUT_SECONDS,
) -> None:
    """Capture the current cube state as a local baseline for move-only tracking."""

    try:
        candidate = asyncio.run(
            resolve_rubiks_connected_x_candidate(
                address=address,
                timeout_seconds=scan_seconds,
            )
        )
        notification = asyncio.run(
            request_rubiks_connected_x_state(
                address=candidate.address,
                timeout_seconds=timeout,
            )
        )
    except Exception:
        logger.exception("Rubik's Connected X baseline capture failed.")
        raise typer.Exit(code=1)

    if notification is None or notification.parsed_message is None:
        typer.echo("No full state-sync frame received.")
        typer.echo(
            "Wake the cube, keep it still for a moment, and try again while the cube is nearby."
        )
        raise typer.Exit(code=1)

    facelets = notification.parsed_message.facelets
    if facelets is None:
        typer.echo("The cube did not return a facelet state.")
        raise typer.Exit(code=1)

    if output == DEFAULT_BASELINE_OUTPUT_PATH:
        saved_path = save_rubiks_connected_x_baseline_facelets(facelets)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{facelets}\n", encoding="utf-8")
        saved_path = output

    typer.echo(render_candidate_line(candidate))
    typer.echo(f"Saved baseline facelets to {saved_path.resolve()}")
    typer.echo("")
    typer.echo("The visualizer will auto-load that baseline on the next normal run.")


@app.command("show-baseline")
def show_baseline_command() -> None:
    """Print the saved baseline and the baked-in gesture that refreshes it."""

    typer.echo(f"Baseline path: {rubiks_connected_x_baseline_path().resolve()}")
    typer.echo(
        "Capture gesture: " + " ".join(RUBIKS_CONNECTED_X_BASELINE_CAPTURE_GESTURE)
    )
    facelets = load_rubiks_connected_x_baseline_facelets()
    if facelets is None:
        typer.echo("No saved baseline found.")
        raise typer.Exit(code=1)
    typer.echo("")
    typer.echo("Saved baseline faces:")
    typer.echo(_render_state_summary(facelets))


def _normalize_calibration_moves(moves: list[str] | None) -> tuple[str, ...]:
    if not moves:
        return DEFAULT_CALIBRATION_MOVES
    normalized = tuple(move.strip() for move in moves if move.strip())
    if not normalized:
        return DEFAULT_CALIBRATION_MOVES
    return normalized


def _render_calibration_summary(
    move_label: str,
    notifications: list[RubiksConnectedXNotification],
) -> str:
    packet_summaries = summarize_rubiks_connected_x_notifications(notifications)
    if not notifications:
        return f"{move_label}: no packets captured"
    if not packet_summaries:
        return f"{move_label}: total={len(notifications)} parsed=0"
    summary_text = ", ".join(
        (
            f"opcode={summary.opcode} face={summary.face_index} "
            f"turn={summary.turn_code} checksum="
            f"{'ok' if summary.is_checksum_valid else 'bad'} x{summary.count}"
        )
        for summary in packet_summaries
    )
    return f"{move_label}: total={len(notifications)} {summary_text}"


def _build_calibration_callback(
    move_label: str,
    *,
    live_packets: bool,
) -> tuple[callable[[RubiksConnectedXNotification], None], dict[str, bool]]:
    state = {"seen_first_packet": False}

    def _callback(notification: RubiksConnectedXNotification) -> None:
        if not state["seen_first_packet"]:
            state["seen_first_packet"] = True
            typer.echo(f"First packet received for {move_label}.")
        if live_packets:
            typer.echo(render_notification_line(notification))

    return _callback, state


def _capture_move_window(
    *,
    address: str,
    move_label: str,
    seconds: float,
    scan_seconds: float,
    live_packets: bool,
) -> tuple[list[RubiksConnectedXNotification], bool]:
    callback, state = _build_calibration_callback(
        move_label,
        live_packets=live_packets,
    )
    notifications = asyncio.run(
        monitor_rubiks_connected_x_notifications(
            address=address,
            seconds=seconds,
            timeout_seconds=scan_seconds,
            on_notification=callback,
        )
    )
    return notifications, state["seen_first_packet"]


@app.command("calibrate")
def calibrate_command(
    address: Annotated[
        str | None,
        typer.Option("--address", help="Specific BLE address to calibrate."),
    ] = None,
    seconds: Annotated[
        float,
        typer.Option("--seconds", help="How long to capture packets for each move."),
    ] = DEFAULT_CALIBRATION_SECONDS,
    move: Annotated[
        list[str] | None,
        typer.Option(
            "--move",
            help="Move label to capture; can be repeated. Defaults to U, U', R, R', F, F'.",
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", help="Where to write the calibration JSON report."),
    ] = DEFAULT_CALIBRATION_OUTPUT_PATH,
    warmup_seconds: Annotated[
        float,
        typer.Option(
            "--warmup-seconds",
            help="How long to spend in the initial warmup capture before labeled moves.",
        ),
    ] = DEFAULT_CALIBRATION_WARMUP_SECONDS,
    live_packets: Annotated[
        bool,
        typer.Option(
            "--live-packets/--no-live-packets",
            help="Print each raw packet while the capture window is open.",
        ),
    ] = True,
    scan_seconds: Annotated[
        float,
        typer.Option(
            "--scan-seconds",
            help="How long to scan when auto-selecting a cube.",
        ),
    ] = DEFAULT_SCAN_TIMEOUT_SECONDS,
) -> None:
    """Walk through labeled cube turns and save grouped packet captures."""

    selected_moves = _normalize_calibration_moves(move)
    try:
        candidate = asyncio.run(
            resolve_rubiks_connected_x_candidate(
                address=address,
                timeout_seconds=scan_seconds,
            )
        )
    except Exception:
        logger.exception("Rubik's Connected X calibration setup failed.")
        raise typer.Exit(code=1)

    typer.echo(f"Calibrating cube at {candidate.address}.")
    typer.echo(
        f"Each capture window lasts {seconds:.1f}s. Perform exactly one labeled move when prompted."
    )
    typer.echo("Keep pauses between moves so the grouped output stays easy to decode.")
    typer.echo(
        "A warmup capture runs first because this cube sometimes needs a move or two before notifications start flowing."
    )

    while True:
        typer.echo("")
        typer.echo("Warmup")
        typer.echo(
            f"Press Enter, then do 1-2 casual quarter turns during the next {warmup_seconds:.1f}s."
        )
        typer.echo(
            "Wait for the 'First packet received for warmup.' message before assuming the link is live."
        )
        typer.prompt(
            "Press Enter to start warmup capture",
            default="",
            show_default=False,
        )
        typer.echo("Warmup capture live. Move the cube now.")
        try:
            warmup_notifications, _ = _capture_move_window(
                address=candidate.address,
                move_label="warmup",
                seconds=warmup_seconds,
                scan_seconds=scan_seconds,
                live_packets=live_packets,
            )
        except Exception:
            logger.exception("Rubik's Connected X warmup capture failed.")
            raise typer.Exit(code=1)

        typer.echo(_render_calibration_summary("warmup", warmup_notifications))
        if warmup_notifications:
            break
        typer.echo("No packets captured during warmup.")
        if not typer.confirm("Retry warmup?", default=True):
            raise typer.Exit(code=1)

    move_results: list[dict[str, object]] = []
    for index, move_label in enumerate(selected_moves, start=1):
        while True:
            typer.echo("")
            typer.echo(f"Move {index}/{len(selected_moves)}: {move_label}")
            typer.echo(
                f"Press Enter to start the {move_label} capture, then do exactly one {move_label} turn."
            )
            typer.echo(
                f"The capture window stays open for {seconds:.1f}s and will confirm when the first packet arrives."
            )
            typer.prompt(
                f"Press Enter to start capture for {move_label}",
                default="",
                show_default=False,
            )
            typer.echo(f"Capture live for {move_label}. Perform the move now.")
            try:
                captured_notifications, _ = _capture_move_window(
                    address=candidate.address,
                    move_label=move_label,
                    seconds=seconds,
                    scan_seconds=scan_seconds,
                    live_packets=live_packets,
                )
            except Exception:
                logger.exception(
                    "Rubik's Connected X calibration capture failed for move %s.",
                    move_label,
                )
                raise typer.Exit(code=1)

            typer.echo(_render_calibration_summary(move_label, captured_notifications))
            if captured_notifications:
                break
            typer.echo(f"No packets captured for {move_label}.")
            if not typer.confirm(f"Retry {move_label}?", default=True):
                break

        packet_summaries = summarize_rubiks_connected_x_notifications(
            captured_notifications
        )
        move_results.append(
            {
                "move_label": move_label,
                "notification_count": len(captured_notifications),
                "notifications": [
                    serialize_rubiks_connected_x_notification(notification)
                    for notification in captured_notifications
                ],
                "packet_summaries": [
                    {
                        "opcode": summary.opcode,
                        "face_index": summary.face_index,
                        "turn_code": summary.turn_code,
                        "is_checksum_valid": summary.is_checksum_valid,
                        "count": summary.count,
                    }
                    for summary in packet_summaries
                ],
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "address": candidate.address,
        "capture_seconds": seconds,
        "moves": list(selected_moves),
        "results": move_results,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo("")
    typer.echo(f"Wrote calibration report to {output}.")
