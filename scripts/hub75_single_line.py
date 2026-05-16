"""Drive one lit line through the heart_rgb_matrix_driver Pi 5 path for panel bring-up.

This is narrower than ``hub75_color_cycle.py`` on purpose. A full-frame solid
fill can fail in many visually ambiguous ways: ghosting, row-address mistakes,
blanking mistakes, or a scan cadence that is simply too hard to perceive.

This script renders exactly one horizontal line and keeps resubmitting that
same frame. If the Pi 5 path can hold a single line steadily, that is a much
better foundation for debugging the rest of the scan waveform.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import Any, Final

from PIL import Image

from heart.device.rgb_display.runtime import _load_matrix_runtime_module
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_PANEL_ROWS: Final[int] = 64
DEFAULT_PANEL_COLS: Final[int] = 64
DEFAULT_CHAIN_LENGTH: Final[int] = 1
DEFAULT_PARALLEL: Final[int] = 1
DEFAULT_HARDWARE_MAPPING: Final[str] = "adafruit-hat-pwm"
DEFAULT_LED_RGB_SEQUENCE: Final[str] = "RGB"
DEFAULT_ROW_INDEX: Final[int] = 0
DEFAULT_LINE_THICKNESS: Final[int] = 1
DEFAULT_HOLD_SECONDS: Final[float] = 8.0
DEFAULT_RESUBMIT_INTERVAL_SECONDS: Final[float] = 0.0
DEFAULT_ITERATIONS: Final[int] = 0
RGBA_IMAGE_MODE: Final[str] = "RGBA"
ALPHA_OPAQUE: Final[int] = 255
HARDWARE_MAPPING_CHOICES: Final[tuple[str, ...]] = ("adafruit-hat", "adafruit-hat-pwm")
WIRING_PROFILE_NAMES: Final[dict[str, str]] = {
    "adafruit-hat": "AdafruitHat",
    "adafruit-hat-pwm": "AdafruitHatPwm",
}


@dataclass(frozen=True)
class LinePattern:
    """Describe the single-line frame we keep alive during bring-up."""

    row_index: int
    thickness: int
    rgba: tuple[int, int, int, int]


def main() -> int:
    """Run the single-line Pi 5 bring-up test."""

    args = parse_args()
    matrix = build_matrix(args)
    pattern = LinePattern(
        row_index=args.row_index,
        thickness=args.line_thickness,
        rgba=(args.red, args.green, args.blue, ALPHA_OPAQUE),
    )

    logger.info(
        "Starting HUB75 single-line test: %sx%s chain=%s parallel=%s row=%s thickness=%s rgb=(%s,%s,%s) backend=%s hold=%.2fs iterations=%s",
        args.rows,
        args.cols,
        args.chain_length,
        args.parallel,
        args.row_index,
        args.line_thickness,
        args.red,
        args.green,
        args.blue,
        backend_name(matrix),
        args.hold_seconds,
        "infinite" if args.iterations == 0 else args.iterations,
    )

    try:
        run_single_line_test(
            matrix=matrix,
            pattern=pattern,
            hold_seconds=args.hold_seconds,
            resubmit_interval_seconds=args.resubmit_interval_seconds,
            iterations=args.iterations,
        )
    except KeyboardInterrupt:
        logger.info("Stopping HUB75 single-line test on keyboard interrupt.")
    finally:
        matrix.close()

    return 0


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the single-line bring-up test."""

    parser = argparse.ArgumentParser(
        description="Render one horizontal line repeatedly through the heart_rgb_matrix_driver Pi 5 path."
    )
    parser.add_argument("--rows", type=int, default=DEFAULT_PANEL_ROWS)
    parser.add_argument("--cols", type=int, default=DEFAULT_PANEL_COLS)
    parser.add_argument("--chain-length", type=int, default=DEFAULT_CHAIN_LENGTH)
    parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)
    parser.add_argument(
        "--hardware-mapping",
        type=str,
        default=DEFAULT_HARDWARE_MAPPING,
        choices=HARDWARE_MAPPING_CHOICES,
    )
    parser.add_argument("--led-rgb-sequence", type=str, default=DEFAULT_LED_RGB_SEQUENCE)
    parser.add_argument("--row-index", type=int, default=DEFAULT_ROW_INDEX)
    parser.add_argument("--line-thickness", type=int, default=DEFAULT_LINE_THICKNESS)
    parser.add_argument("--red", type=int, default=255)
    parser.add_argument("--green", type=int, default=255)
    parser.add_argument("--blue", type=int, default=255)
    parser.add_argument("--hold-seconds", type=float, default=DEFAULT_HOLD_SECONDS)
    parser.add_argument(
        "--resubmit-interval-seconds",
        type=float,
        default=DEFAULT_RESUBMIT_INTERVAL_SECONDS,
        help="Delay between repeated submit_rgba() calls. Use 0 to hammer continuously.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="How many times to hold the same line pattern. Use 0 to loop until interrupted.",
    )
    return parser.parse_args()


def build_native_driver(args: argparse.Namespace) -> Any:
    """Build the raw heart_rgb_matrix_driver from CLI arguments."""

    native_module = _load_matrix_runtime_module()
    wiring_profile_name = WIRING_PROFILE_NAMES[args.hardware_mapping]
    config = native_module.MatrixConfig(
        wiring=getattr(native_module.WiringProfile, wiring_profile_name),
        panel_rows=args.rows,
        panel_cols=args.cols,
        chain_length=args.chain_length,
        parallel=args.parallel,
        color_order=getattr(native_module.ColorOrder, args.led_rgb_sequence.upper()),
    )
    return native_module.MatrixDriver(config)


def build_matrix(args: argparse.Namespace) -> Any:
    """Build the direct heart_rgb_matrix_driver used by the Pi 5 bring-up scripts."""

    return build_native_driver(args)


def run_single_line_test(
    matrix: Any,
    pattern: LinePattern,
    hold_seconds: float,
    resubmit_interval_seconds: float,
    iterations: int,
) -> None:
    """Keep one horizontal line alive on the panel for the requested duration."""

    image = build_line_image(matrix.width, matrix.height, pattern)
    rgba_bytes = image.tobytes()
    total_cycles = iterations if iterations > 0 else None
    completed_cycles = 0

    while total_cycles is None or completed_cycles < total_cycles:
        hold_pattern(
            matrix=matrix,
            rgba_bytes=rgba_bytes,
            row_index=pattern.row_index,
            thickness=pattern.thickness,
            rgb=pattern.rgba[:3],
            hold_seconds=hold_seconds,
            resubmit_interval_seconds=resubmit_interval_seconds,
        )
        completed_cycles += 1


def build_line_image(width: int, height: int, pattern: LinePattern) -> Image.Image:
    """Create the one-line RGBA frame submitted to the Pi 5 backend."""

    if pattern.row_index < 0 or pattern.row_index >= height:
        raise ValueError(f"Row index {pattern.row_index} is outside image height {height}.")
    if pattern.thickness <= 0:
        raise ValueError("line_thickness must be at least 1.")

    image = Image.new(RGBA_IMAGE_MODE, (width, height), color=(0, 0, 0, ALPHA_OPAQUE))
    bottom = min(height, pattern.row_index + pattern.thickness)
    for row in range(pattern.row_index, bottom):
        for column in range(width):
            image.putpixel((column, row), pattern.rgba)
    return image


def hold_pattern(
    matrix: Any,
    rgba_bytes: bytes,
    row_index: int,
    thickness: int,
    rgb: tuple[int, int, int],
    hold_seconds: float,
    resubmit_interval_seconds: float,
) -> None:
    """Submit the same one-line frame repeatedly for the hold window."""

    deadline = time.monotonic() + hold_seconds
    submit_count = 0

    while True:
        matrix.submit_rgba(rgba_bytes, matrix.width, matrix.height)
        submit_count += 1
        if time.monotonic() >= deadline:
            break
        if resubmit_interval_seconds > 0:
            time.sleep(resubmit_interval_seconds)

    logger.info(
        "Displayed line row=%s thickness=%s rgb=%s with %s submits over %.2fs",
        row_index,
        thickness,
        rgb,
        submit_count,
        hold_seconds,
    )


def backend_name(matrix: Any) -> str:
    """Return the native backend identifier for diagnostics."""

    stats = matrix.stats()
    return str(stats.backend_name)


if __name__ == "__main__":
    raise SystemExit(main())
