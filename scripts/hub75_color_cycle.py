"""Cycle a HUB75 panel through RGB primaries at multiple intensities.

This is a deliberately small panel sanity test for the clean-room
heart_rgb_matrix_driver
stack. It uses the direct ``submit_rgba()`` API so the script works even when
the higher-level Python canvas compatibility layer is not the active import
surface on the target Pi. The visual pattern stays simple enough to diagnose
wiring or color-order problems quickly on real hardware.
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
DEFAULT_STEP_HOLD_SECONDS: Final[float] = 0.75
DEFAULT_RESUBMIT_INTERVAL_SECONDS: Final[float] = 0.05
DEFAULT_ITERATIONS: Final[int] = 0
DEFAULT_INTENSITIES: Final[tuple[int, ...]] = (32, 96, 160, 255)
RGBA_IMAGE_MODE: Final[str] = "RGBA"
ALPHA_OPAQUE: Final[int] = 255
KERNEL_LOOP_BACKEND_TOKEN: Final[str] = "kernel-loop"
HARDWARE_MAPPING_CHOICES: Final[tuple[str, ...]] = ("adafruit-hat", "adafruit-hat-pwm")
WIRING_PROFILE_NAMES: Final[dict[str, str]] = {
    "adafruit-hat": "AdafruitHat",
    "adafruit-hat-pwm": "AdafruitHatPwm",
}


@dataclass(frozen=True)
class ColorStep:
    name: str
    rgba: tuple[int, int, int, int]


def main() -> int:
    """Run the panel color-cycle sanity test."""

    args = parse_args()
    matrix = build_matrix(args)
    steps = build_color_steps(parse_intensities(args.intensities))

    logger.info(
        "Starting HUB75 color cycle: %sx%s chain=%s parallel=%s mapping=%s rgb=%s backend=%s steps=%s hold=%.2fs iterations=%s",
        args.rows,
        args.cols,
        args.chain_length,
        args.parallel,
        args.hardware_mapping,
        args.led_rgb_sequence,
        backend_name(matrix),
        len(steps),
        args.step_hold_seconds,
        "infinite" if args.iterations == 0 else args.iterations,
    )

    try:
        run_color_cycle(
            matrix=matrix,
            steps=steps,
            step_hold_seconds=args.step_hold_seconds,
            resubmit_interval_seconds=args.resubmit_interval_seconds,
            iterations=args.iterations,
        )
    except KeyboardInterrupt:
        logger.info("Stopping HUB75 color cycle on keyboard interrupt.")
    finally:
        matrix.close()

    return 0


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the panel sanity test."""

    parser = argparse.ArgumentParser(
        description="Cycle a HUB75 display through red, green, and blue at several intensities."
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
    parser.add_argument("--step-hold-seconds", type=float, default=DEFAULT_STEP_HOLD_SECONDS)
    parser.add_argument(
        "--resubmit-interval-seconds",
        type=float,
        default=DEFAULT_RESUBMIT_INTERVAL_SECONDS,
        help=(
            "Delay between repeated submit_rgba() calls while holding one color step. "
            "Increase this to slow the Pi 5 one-shot path down for bring-up debugging."
        ),
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="How many full RGB cycles to run. Use 0 to loop until interrupted.",
    )
    parser.add_argument(
        "--intensities",
        type=str,
        default=",".join(str(value) for value in DEFAULT_INTENSITIES),
        help="Comma-separated 0..255 intensities, for example 32,96,160,255.",
    )
    return parser.parse_args()


def build_native_driver(args: argparse.Namespace) -> Any:
    """Build the raw heart_rgb_matrix_driver when the canvas wrapper is unavailable."""

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
    """Build the direct heart_rgb_matrix_driver from CLI arguments."""

    return build_native_driver(args)


def parse_intensities(raw_intensities: str) -> tuple[int, ...]:
    """Parse and validate the requested intensity sweep."""

    intensity_values = tuple(
        int(component.strip())
        for component in raw_intensities.split(",")
        if component.strip()
    )
    if not intensity_values:
        raise ValueError("At least one intensity value is required.")
    for intensity in intensity_values:
        if intensity < 0 or intensity > 255:
            raise ValueError(
                f"Intensity {intensity} is out of range; expected values between 0 and 255."
            )
    return intensity_values


def build_color_steps(intensities: tuple[int, ...]) -> tuple[ColorStep, ...]:
    """Build the ordered RGB primary/intensity sequence."""

    steps: list[ColorStep] = []
    for intensity in intensities:
        steps.extend(
            (
                ColorStep("red", (intensity, 0, 0, ALPHA_OPAQUE)),
                ColorStep("green", (0, intensity, 0, ALPHA_OPAQUE)),
                ColorStep("blue", (0, 0, intensity, ALPHA_OPAQUE)),
            )
        )
    return tuple(steps)


def run_color_cycle(
    matrix: Any,
    steps: tuple[ColorStep, ...],
    step_hold_seconds: float,
    resubmit_interval_seconds: float,
    iterations: int,
) -> None:
    """Present each requested step for the configured duration."""

    total_cycles = iterations if iterations > 0 else None
    completed_cycles = 0

    while total_cycles is None or completed_cycles < total_cycles:
        for step in steps:
            hold_step(
                matrix=matrix,
                step=step,
                step_hold_seconds=step_hold_seconds,
                resubmit_interval_seconds=resubmit_interval_seconds,
            )
        completed_cycles += 1


def hold_step(
    matrix: Any,
    step: ColorStep,
    step_hold_seconds: float,
    resubmit_interval_seconds: float,
) -> None:
    """Keep one solid color alive on one-shot transports for the full hold interval."""

    image = Image.new(
        RGBA_IMAGE_MODE,
        (matrix.width, matrix.height),
        color=step.rgba,
    )
    rgba_bytes = image.tobytes()
    if backend_owns_persistent_refresh(matrix):
        matrix.submit_rgba(rgba_bytes, matrix.width, matrix.height)
        logger.info(
            "Displayed %s step rgba=%s with 1 submit over %.2fs on persistent backend %s",
            step.name,
            step.rgba[:3],
            step_hold_seconds,
            backend_name(matrix),
        )
        time.sleep(step_hold_seconds)
        return

    deadline = time.monotonic() + step_hold_seconds
    submit_count = 0

    while True:
        matrix.submit_rgba(rgba_bytes, matrix.width, matrix.height)
        submit_count += 1
        if time.monotonic() >= deadline:
            break
        time.sleep(resubmit_interval_seconds)

    logger.info(
        "Displayed %s step rgba=%s with %s submits over %.2fs",
        step.name,
        step.rgba[:3],
        submit_count,
        step_hold_seconds,
    )


def backend_name(matrix: Any) -> str:
    """Return the native backend identifier when the driver exposes runtime stats."""

    stats = matrix.stats()
    return str(stats.backend_name)


def backend_owns_persistent_refresh(matrix: Any) -> bool:
    """Return whether the active backend keeps scanning after one submit."""

    return KERNEL_LOOP_BACKEND_TOKEN in backend_name(matrix)


if __name__ == "__main__":
    raise SystemExit(main())
