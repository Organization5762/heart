"""Fast-path helpers for the common FlowToy set-mode CLI workflow."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Sequence

FLOWTOY_LFO_ACTIVE_BIT = 1 << 0
FLOWTOY_HUE_ACTIVE_BIT = 1 << 1
FLOWTOY_SATURATION_ACTIVE_BIT = 1 << 2
FLOWTOY_BRIGHTNESS_ACTIVE_BIT = 1 << 3
FLOWTOY_SPEED_ACTIVE_BIT = 1 << 4
FLOWTOY_DENSITY_ACTIVE_BIT = 1 << 5


@dataclass(frozen=True, slots=True)
class FastFlowToyCommand:
    """Minimal command payload for direct FlowToy serial writes."""

    port: str
    command: str
    summary: str


DEFAULT_SERIAL_BAUDRATE = 115_200


def _active_bit_from_name(name: str) -> int:
    return {
        "hue_offset": FLOWTOY_HUE_ACTIVE_BIT,
        "saturation": FLOWTOY_SATURATION_ACTIVE_BIT,
        "brightness": FLOWTOY_BRIGHTNESS_ACTIVE_BIT,
        "speed": FLOWTOY_SPEED_ACTIVE_BIT,
        "density": FLOWTOY_DENSITY_ACTIVE_BIT,
    }[name]


def _parse_int_option(arguments: Sequence[str], option: str) -> int | None:
    try:
        index = arguments.index(option)
    except ValueError:
        return None
    if index + 1 >= len(arguments):
        raise ValueError(f"Missing value for {option}")
    return int(arguments[index + 1])


def _parse_str_option(arguments: Sequence[str], option: str) -> str | None:
    try:
        index = arguments.index(option)
    except ValueError:
        return None
    if index + 1 >= len(arguments):
        raise ValueError(f"Missing value for {option}")
    return arguments[index + 1]


def parse_fast_flowtoy_set_mode(arguments: Sequence[str]) -> FastFlowToyCommand | None:
    """Parse a direct FlowToy set-mode command when it fits the fast path."""

    if len(arguments) < 3 or arguments[0] != "flowtoy" or arguments[1] != "set-mode":
        return None
    if any(
        option in arguments
        for option in (
            "--help",
            "--brightness-scan-start",
            "--brightness-scan-end",
            "--observe-seconds",
        )
    ):
        return None

    port = _parse_str_option(arguments, "--port")
    group_id = _parse_int_option(arguments, "--group-id")
    page = _parse_int_option(arguments, "--page")
    mode = _parse_int_option(arguments, "--mode")
    if port is None or group_id is None or page is None or mode is None:
        return None
    if page < 1 or mode < 1:
        raise ValueError("Page and mode must be 1-based user-facing values")

    actives = _parse_int_option(arguments, "--actives")
    hue_offset = _parse_int_option(arguments, "--hue-offset")
    saturation = _parse_int_option(arguments, "--saturation")
    brightness = _parse_int_option(arguments, "--brightness")
    speed = _parse_int_option(arguments, "--speed")
    density = _parse_int_option(arguments, "--density")

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

    fields = (
        group_id,
        page - 1,
        mode - 1,
        resolved_actives,
        int(hue_offset or 0),
        int(saturation or 0),
        int(brightness or 0),
        int(speed or 0),
        int(density or 0),
        0,
        0,
        0,
        0,
    )
    command = "p" + ",".join(str(int(value)) for value in fields)
    summary = (
        f"Sent {command} on {port} "
        f"(group_id={group_id}, user_page={page}, user_mode={mode}, "
        f"actives={resolved_actives}, hue_offset={int(hue_offset or 0)}, "
        f"saturation={int(saturation or 0)}, brightness={int(brightness or 0)}, "
        f"speed={int(speed or 0)}, density={int(density or 0)})."
    )
    return FastFlowToyCommand(port=port, command=command, summary=summary)


def send_fast_flowtoy_command(command: FastFlowToyCommand) -> None:
    """Write a single FlowToy command directly to the target serial port."""

    import serial

    with serial.Serial(command.port, DEFAULT_SERIAL_BAUDRATE, timeout=1) as handle:
        send_fast_flowtoy_command_on_handle(handle, command.command)


def send_fast_flowtoy_command_on_handle(handle: object, command: str) -> None:
    """Write one FlowToy command to an already-open serial handle."""

    encoded_command = command.encode("utf-8") + b"\n"
    handle.write(encoded_command)
    handle.flush()


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lightweight FlowToy serial commands without Typer startup."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_mode_parser = subparsers.add_parser(
        "set-mode",
        help="Send one FlowToy set-mode packet directly over serial.",
    )
    set_mode_parser.add_argument("--port", required=True)
    set_mode_parser.add_argument("--group-id", required=True, type=int)
    set_mode_parser.add_argument("--page", required=True, type=int)
    set_mode_parser.add_argument("--mode", required=True, type=int)
    set_mode_parser.add_argument("--actives", type=int)
    set_mode_parser.add_argument("--hue-offset", type=int)
    set_mode_parser.add_argument("--saturation", type=int)
    set_mode_parser.add_argument("--brightness", type=int)
    set_mode_parser.add_argument("--speed", type=int)
    set_mode_parser.add_argument("--density", type=int)

    shell_parser = subparsers.add_parser(
        "shell",
        help="Open a persistent serial shell for raw FlowToy commands.",
    )
    shell_parser.add_argument("--port", required=True)

    return parser


def _command_from_namespace(namespace: argparse.Namespace) -> FastFlowToyCommand:
    arguments = [
        "flowtoy",
        "set-mode",
        "--port",
        str(namespace.port),
        "--group-id",
        str(namespace.group_id),
        "--page",
        str(namespace.page),
        "--mode",
        str(namespace.mode),
    ]
    for option_name, option_flag in (
        ("actives", "--actives"),
        ("hue_offset", "--hue-offset"),
        ("saturation", "--saturation"),
        ("brightness", "--brightness"),
        ("speed", "--speed"),
        ("density", "--density"),
    ):
        value = getattr(namespace, option_name)
        if value is None:
            continue
        arguments.extend([option_flag, str(value)])

    parsed_command = parse_fast_flowtoy_set_mode(arguments)
    if parsed_command is None:
        raise ValueError("Unable to parse fast FlowToy command")
    return parsed_command


def _run_shell(port: str) -> int:
    import serial

    print(f"FlowToy fast shell on {port}. Type 'exit' to quit.")
    print("Raw command example: p2575,0,5,8,0,0,80,0,0,0,0,0,0")
    print("Set-mode example: set-mode --group-id 2575 --page 1 --mode 6 --brightness 80")
    with serial.Serial(port, DEFAULT_SERIAL_BAUDRATE, timeout=1) as handle:
        while True:
            try:
                line = input("flowtoy> ").strip()
            except EOFError:
                print("")
                return 0
            except KeyboardInterrupt:
                print("")
                return 0

            if not line:
                continue
            if line in {"exit", "quit"}:
                return 0
            if line == "help":
                print("Raw command example: p2575,0,5,8,0,0,80,0,0,0,0,0,0")
                print(
                    "Set-mode example: set-mode --group-id 2575 --page 1 --mode 6 --brightness 80"
                )
                continue
            if line.startswith("set-mode "):
                parsed_command = parse_fast_flowtoy_set_mode(
                    ("flowtoy " + line + f" --port {port}").split()
                )
                if parsed_command is None:
                    print(
                        "Error: shell set-mode supports explicit --group-id/--page/--mode and direct override flags only."
                    )
                    continue
                send_fast_flowtoy_command_on_handle(handle, parsed_command.command)
                print(parsed_command.summary)
                continue

            send_fast_flowtoy_command_on_handle(handle, line)
            print(f"Sent {line} on {port}.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    if args.command == "set-mode":
        command = _command_from_namespace(args)
        send_fast_flowtoy_command(command)
        print(command.summary)
        return 0

    if args.command == "shell":
        return _run_shell(args.port)

    parser.error(f"Unsupported command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
