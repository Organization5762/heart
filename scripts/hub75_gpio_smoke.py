"""Direct GPIO HUB75 smoke test for Raspberry Pi bring-up.

This intentionally bypasses the heart_rgb_matrix_driver Pi 5 transport and bit-bangs the
bonnet pinout directly through RPi.GPIO. The goal is not performance or low
CPU usage. The goal is to answer one narrow question during bring-up:

    "Can this Pi/bonnet/panel combination show a simple image at all if we
    drive the HUB75 control lines ourselves?"

The script continuously scans all row pairs with a solid RGB color and can
cycle colors after a configurable hold interval. If this works while the Pi 5
PIO path stays black, the remaining bug is in the transport waveform rather
than the basic GPIO-to-panel wiring.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import Final

import RPi.GPIO as GPIO

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_PANEL_ROWS: Final[int] = 64
DEFAULT_PANEL_COLS: Final[int] = 64
DEFAULT_FRAME_HOLD_SECONDS: Final[float] = 3.0
DEFAULT_ROW_DWELL_SECONDS: Final[float] = 0.0005
DEFAULT_ITERATIONS: Final[int] = 0
DEFAULT_INTENSITY: Final[int] = 255
DEFAULT_SINGLE_COLOR: Final[str | None] = None
PWM_THRESHOLD: Final[int] = 128

R1_GPIO: Final[int] = 5
G1_GPIO: Final[int] = 13
B1_GPIO: Final[int] = 6
R2_GPIO: Final[int] = 12
G2_GPIO: Final[int] = 16
B2_GPIO: Final[int] = 23

A_GPIO: Final[int] = 22
B_GPIO: Final[int] = 26
C_GPIO: Final[int] = 27
D_GPIO: Final[int] = 20
E_GPIO: Final[int] = 24

CLK_GPIO: Final[int] = 17
LAT_GPIO: Final[int] = 21
OE_GPIO: Final[int] = 18

RGB_GPIOS: Final[tuple[int, ...]] = (
    R1_GPIO,
    G1_GPIO,
    B1_GPIO,
    R2_GPIO,
    G2_GPIO,
    B2_GPIO,
)
ADDR_GPIOS: Final[tuple[int, ...]] = (A_GPIO, B_GPIO, C_GPIO, D_GPIO, E_GPIO)
CONTROL_GPIOS: Final[tuple[int, ...]] = (CLK_GPIO, LAT_GPIO, OE_GPIO)
ALL_GPIOS: Final[tuple[int, ...]] = RGB_GPIOS + ADDR_GPIOS + CONTROL_GPIOS


@dataclass(frozen=True)
class ColorStep:
    name: str
    top_rgb: tuple[bool, bool, bool]
    bottom_rgb: tuple[bool, bool, bool]


def main() -> int:
    """Run the direct GPIO HUB75 smoke test."""

    args = parse_args()
    color_steps = build_color_steps(args.intensity, args.single_color)
    configure_gpio()

    logger.info(
        "Starting direct GPIO HUB75 smoke test: rows=%s cols=%s hold=%.2fs row_dwell=%.6fs iterations=%s",
        args.rows,
        args.cols,
        args.frame_hold_seconds,
        args.row_dwell_seconds,
        "infinite" if args.iterations == 0 else args.iterations,
    )

    try:
        run_color_cycle(
            panel_rows=args.rows,
            panel_cols=args.cols,
            color_steps=color_steps,
            frame_hold_seconds=args.frame_hold_seconds,
            row_dwell_seconds=args.row_dwell_seconds,
            iterations=args.iterations,
        )
    except KeyboardInterrupt:
        logger.info("Stopping direct GPIO HUB75 smoke test on keyboard interrupt.")
    finally:
        blank_panel()
        GPIO.cleanup()

    return 0


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the direct GPIO bring-up script."""

    parser = argparse.ArgumentParser(
        description="Bit-bang a HUB75 panel directly through Raspberry Pi GPIO pins."
    )
    parser.add_argument("--rows", type=int, default=DEFAULT_PANEL_ROWS)
    parser.add_argument("--cols", type=int, default=DEFAULT_PANEL_COLS)
    parser.add_argument("--frame-hold-seconds", type=float, default=DEFAULT_FRAME_HOLD_SECONDS)
    parser.add_argument("--row-dwell-seconds", type=float, default=DEFAULT_ROW_DWELL_SECONDS)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--intensity", type=int, default=DEFAULT_INTENSITY)
    parser.add_argument(
        "--single-color",
        choices=("red", "green", "blue", "white"),
        default=DEFAULT_SINGLE_COLOR,
    )
    return parser.parse_args()


def build_color_steps(intensity: int, single_color: str | None) -> tuple[ColorStep, ...]:
    """Build the simple RGB cycle used for bring-up."""

    level_on = intensity >= PWM_THRESHOLD
    steps = (
        ColorStep("red", (level_on, False, False), (level_on, False, False)),
        ColorStep("green", (False, level_on, False), (False, level_on, False)),
        ColorStep("blue", (False, False, level_on), (False, False, level_on)),
        ColorStep("white", (level_on, level_on, level_on), (level_on, level_on, level_on)),
    )
    if single_color is None:
        return steps
    return tuple(step for step in steps if step.name == single_color)


def configure_gpio() -> None:
    """Initialize GPIO outputs in a conservative blanked state."""

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for gpio in ALL_GPIOS:
        GPIO.setup(gpio, GPIO.OUT, initial=GPIO.LOW)
    GPIO.output(OE_GPIO, GPIO.HIGH)
    GPIO.output(LAT_GPIO, GPIO.LOW)
    GPIO.output(CLK_GPIO, GPIO.LOW)


def run_color_cycle(
    panel_rows: int,
    panel_cols: int,
    color_steps: tuple[ColorStep, ...],
    frame_hold_seconds: float,
    row_dwell_seconds: float,
    iterations: int,
) -> None:
    """Continuously scan the requested colors with a direct row-pair loop."""

    row_pairs = panel_rows // 2
    total_cycles = iterations if iterations > 0 else None
    completed_cycles = 0

    while total_cycles is None or completed_cycles < total_cycles:
        for step in color_steps:
            deadline = time.monotonic() + frame_hold_seconds
            logger.info("Displaying direct GPIO step %s", step.name)
            while time.monotonic() < deadline:
                scan_frame(row_pairs, panel_cols, step, row_dwell_seconds)
        completed_cycles += 1


def scan_frame(
    row_pairs: int,
    panel_cols: int,
    step: ColorStep,
    row_dwell_seconds: float,
) -> None:
    """Scan one full frame worth of row pairs for the current solid color."""

    for row_pair in range(row_pairs):
        GPIO.output(OE_GPIO, GPIO.HIGH)
        set_row_address(row_pair)
        shift_row(panel_cols, step)
        latch_row()
        GPIO.output(OE_GPIO, GPIO.LOW)
        time.sleep(row_dwell_seconds)


def set_row_address(row_pair: int) -> None:
    """Drive the A..E row-address pins for the requested row pair."""

    for bit_index, gpio in enumerate(ADDR_GPIOS):
        GPIO.output(gpio, GPIO.HIGH if (row_pair & (1 << bit_index)) else GPIO.LOW)


def shift_row(panel_cols: int, step: ColorStep) -> None:
    """Shift one row-pair worth of constant RGB data into the panel."""

    for _column in range(panel_cols):
        write_rgb(step)
        GPIO.output(CLK_GPIO, GPIO.HIGH)
        GPIO.output(CLK_GPIO, GPIO.LOW)


def write_rgb(step: ColorStep) -> None:
    """Drive the HUB75 RGB data pins for one shifted column."""

    top_red, top_green, top_blue = step.top_rgb
    bottom_red, bottom_green, bottom_blue = step.bottom_rgb
    GPIO.output(R1_GPIO, GPIO.HIGH if top_red else GPIO.LOW)
    GPIO.output(G1_GPIO, GPIO.HIGH if top_green else GPIO.LOW)
    GPIO.output(B1_GPIO, GPIO.HIGH if top_blue else GPIO.LOW)
    GPIO.output(R2_GPIO, GPIO.HIGH if bottom_red else GPIO.LOW)
    GPIO.output(G2_GPIO, GPIO.HIGH if bottom_green else GPIO.LOW)
    GPIO.output(B2_GPIO, GPIO.HIGH if bottom_blue else GPIO.LOW)


def latch_row() -> None:
    """Pulse LAT once after a full row's worth of columns have been shifted."""

    GPIO.output(LAT_GPIO, GPIO.HIGH)
    GPIO.output(LAT_GPIO, GPIO.LOW)


def blank_panel() -> None:
    """Leave the panel in a safe blanked state when the script exits."""

    GPIO.output(OE_GPIO, GPIO.HIGH)
    GPIO.output(LAT_GPIO, GPIO.LOW)
    GPIO.output(CLK_GPIO, GPIO.LOW)
    for gpio in RGB_GPIOS + ADDR_GPIOS:
        GPIO.output(gpio, GPIO.LOW)


if __name__ == "__main__":
    raise SystemExit(main())
