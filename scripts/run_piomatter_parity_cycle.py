"""Prepare a Piomatter checkout for parity and run the RGB cycle demo."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from heart.utilities.logging import get_logger

LOGGER = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKOUT = Path("/home/michael/tmp/Adafruit_Blinka_Raspberry_Pi5_Piomatter")
DEFAULT_COLOR_INTERVAL_SECONDS = 3.0
DEFAULT_HEIGHT = 64
DEFAULT_HOLD_SECONDS = 9.0
DEFAULT_ITERATIONS = 1
DEFAULT_N_ADDR_LINES = 5
DEFAULT_PINOUT = "adafruit-matrix-bonnet"
DEFAULT_WIDTH = 64
PREPARE_SCRIPT = REPO_ROOT / "scripts" / "prepare_piomatter_parity_checkout.py"
RGB_CYCLE_SCRIPT = REPO_ROOT / "scripts" / "piomatter_rgb_cycle.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optionally patch/reinstall Piomatter, then run the RGB cycle demo."
    )
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument("--skip-prepare", action="store_true")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--n-addr-lines", type=int, default=DEFAULT_N_ADDR_LINES)
    parser.add_argument("--pinout", type=str, default=DEFAULT_PINOUT)
    parser.add_argument(
        "--color-interval-seconds",
        type=float,
        default=DEFAULT_COLOR_INTERVAL_SECONDS,
    )
    parser.add_argument("--hold-seconds", type=float, default=DEFAULT_HOLD_SECONDS)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument(
        "--break-system-packages",
        action="store_true",
        help="Pass Debian's PEP 668 override when reinstalling Piomatter.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.skip_prepare:
        run_command(
            [
                sys.executable,
                str(PREPARE_SCRIPT),
                "--checkout",
                str(args.checkout),
            ]
        )
    if not args.skip_install:
        install_command = [sys.executable, "-m", "pip", "install", "--user", "--force-reinstall"]
        if args.break_system_packages:
            install_command.append("--break-system-packages")
        install_command.append(str(args.checkout))
        run_command(install_command)

    run_command(
        [
            sys.executable,
            str(RGB_CYCLE_SCRIPT),
            "--width",
            str(args.width),
            "--height",
            str(args.height),
            "--n-addr-lines",
            str(args.n_addr_lines),
            "--pinout",
            args.pinout,
            "--hold-seconds",
            str(args.hold_seconds),
            "--color-interval-seconds",
            str(args.color_interval_seconds),
            "--iterations",
            str(args.iterations),
        ]
    )
    return 0


def run_command(command: list[str]) -> None:
    LOGGER.info("Running %s", command)
    subprocess.run(command, check=True, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
