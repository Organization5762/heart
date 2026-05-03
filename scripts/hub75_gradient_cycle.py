"""Render a full-frame blue-to-red gradient through the heart_rgb_matrix_driver Pi 5 path.

This keeps the panel exercise simple while moving beyond the one-line bring-up
probe. The frame is a horizontal gradient with a light-blue bias that slowly
shifts toward red over time, so the whole panel stays active and visual
changes are easy to spot without introducing text or sprite complexity.
"""

from __future__ import annotations

import argparse
import math
import time
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
DEFAULT_FRAME_SECONDS: Final[float] = 0.05
DEFAULT_HOLD_SECONDS: Final[float] = 30.0
DEFAULT_BLUE_BIAS: Final[int] = 96
DEFAULT_RED_AMPLITUDE: Final[int] = 120
DEFAULT_GREEN_LEVEL: Final[int] = 40
DEFAULT_HORIZONTAL_SWEEP_SECONDS: Final[float] = 8.0
RGBA_IMAGE_MODE: Final[str] = "RGBA"
ALPHA_OPAQUE: Final[int] = 255
HARDWARE_MAPPING_CHOICES: Final[tuple[str, ...]] = ("adafruit-hat", "adafruit-hat-pwm")
WIRING_PROFILE_NAMES: Final[dict[str, str]] = {
    "adafruit-hat": "AdafruitHat",
    "adafruit-hat-pwm": "AdafruitHatPwm",
}


def main() -> int:
    """Run the full-frame gradient Pi 5 bring-up test."""

    args = parse_args()
    matrix = build_matrix(args)

    logger.info(
        "Starting HUB75 gradient cycle: %sx%s chain=%s parallel=%s rgb=%s backend=%s hold=%.2fs frame=%.3fs",
        args.rows,
        args.cols,
        args.chain_length,
        args.parallel,
        args.led_rgb_sequence,
        backend_name(matrix),
        args.hold_seconds,
        args.frame_seconds,
    )

    try:
        run_gradient_cycle(
            matrix=matrix,
            hold_seconds=args.hold_seconds,
            frame_seconds=args.frame_seconds,
            blue_bias=args.blue_bias,
            red_amplitude=args.red_amplitude,
            green_level=args.green_level,
            horizontal_sweep_seconds=args.horizontal_sweep_seconds,
        )
    except KeyboardInterrupt:
        logger.info("Stopping HUB75 gradient cycle on keyboard interrupt.")
    finally:
        matrix.close()

    return 0


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the gradient bring-up test."""

    parser = argparse.ArgumentParser(
        description="Render a slow full-screen light-blue to red gradient through the heart_rgb_matrix_driver Pi 5 path."
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
    parser.add_argument("--hold-seconds", type=float, default=DEFAULT_HOLD_SECONDS)
    parser.add_argument("--frame-seconds", type=float, default=DEFAULT_FRAME_SECONDS)
    parser.add_argument("--blue-bias", type=int, default=DEFAULT_BLUE_BIAS)
    parser.add_argument("--red-amplitude", type=int, default=DEFAULT_RED_AMPLITUDE)
    parser.add_argument("--green-level", type=int, default=DEFAULT_GREEN_LEVEL)
    parser.add_argument(
        "--horizontal-sweep-seconds",
        type=float,
        default=DEFAULT_HORIZONTAL_SWEEP_SECONDS,
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


def run_gradient_cycle(
    matrix: Any,
    hold_seconds: float,
    frame_seconds: float,
    blue_bias: int,
    red_amplitude: int,
    green_level: int,
    horizontal_sweep_seconds: float,
) -> None:
    """Render the animated full-frame gradient for the requested duration."""

    start_time = time.monotonic()
    deadline = start_time + hold_seconds
    frame_count = 0

    while True:
        now = time.monotonic()
        if now >= deadline:
            break
        phase = (now - start_time) / horizontal_sweep_seconds
        image = build_gradient_image(
            width=matrix.width,
            height=matrix.height,
            phase=phase,
            blue_bias=blue_bias,
            red_amplitude=red_amplitude,
            green_level=green_level,
        )
        matrix.submit_rgba(image.tobytes(), matrix.width, matrix.height)
        frame_count += 1
        time.sleep(frame_seconds)

    logger.info(
        "Displayed %s gradient frames over %.2fs",
        frame_count,
        hold_seconds,
    )


def build_gradient_image(
    width: int,
    height: int,
    phase: float,
    blue_bias: int,
    red_amplitude: int,
    green_level: int,
) -> Image.Image:
    """Create one full-frame gradient image for the current animation phase."""

    image = Image.new(RGBA_IMAGE_MODE, (width, height), color=(0, 0, 0, ALPHA_OPAQUE))
    phase_offset = 0.5 + 0.5 * math.sin(phase * math.tau)
    max_index = max(width - 1, 1)

    for column in range(width):
        column_mix = column / max_index
        red = clamp_u8(int(32 + red_amplitude * (column_mix + phase_offset) / 2.0))
        blue = clamp_u8(int(blue_bias + (1.0 - column_mix) * 120 - phase_offset * 48))
        green = clamp_u8(int(green_level + (1.0 - abs(column_mix - 0.5) * 2.0) * 24))
        for row in range(height):
            image.putpixel((column, row), (red, green, blue, ALPHA_OPAQUE))
    return image


def clamp_u8(value: int) -> int:
    """Clamp an integer into the 0..255 range expected by RGBA images."""

    return max(0, min(255, value))


def backend_name(matrix: Any) -> str:
    """Return the native backend identifier for diagnostics."""

    stats = matrix.stats()
    return str(stats.backend_name)


if __name__ == "__main__":
    raise SystemExit(main())
