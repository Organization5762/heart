"""Cycle a Piomatter-backed HUB75 panel through red, green, and blue.

This is the external Pi 5 baseline for panel bring-up. It exercises Adafruit's
Piomatter stack directly so Heart can compare panel behavior against a known
working implementation before porting the same behavior into
``heart_rgb_matrix_driver``.
"""

from __future__ import annotations

import argparse
import gc
import time
from dataclasses import dataclass
from typing import Final

import numpy as np

from heart.utilities.logging import get_logger

try:
    import adafruit_blinka_raspberry_pi5_piomatter as piomatter
except ImportError as error:  # pragma: no cover - Pi-only dependency
    raise SystemExit(
        "Piomatter is not installed. Install "
        "Adafruit-Blinka-Raspberry-Pi5-Piomatter on the target Pi."
    ) from error

logger = get_logger(__name__)

DEFAULT_COLOR_INTERVAL_SECONDS: Final[float] = 0.2
DEFAULT_HEIGHT: Final[int] = 64
DEFAULT_HOLD_SECONDS: Final[float] = 6.0
DEFAULT_ITERATIONS: Final[int] = 1
DEFAULT_N_ADDR_LINES: Final[int] = 5
DEFAULT_N_PLANES: Final[int] = 10
DEFAULT_N_TEMPORAL_PLANES: Final[int] = 2
DEFAULT_PINOUT: Final[str] = "adafruit-matrix-bonnet"
DEFAULT_PATTERN: Final[str] = "rgb-cycle"
DEFAULT_WIDTH: Final[int] = 64
PATTERN_CHOICES: Final[tuple[str, ...]] = ("rgb-cycle", "quadrants", "center-box")
PINOUT_CHOICES: Final[tuple[str, ...]] = (
    "adafruit-matrix-bonnet",
    "adafruit-matrix-bonnet-bgr",
    "adafruit-matrix-hat",
    "adafruit-matrix-hat-bgr",
)
PINOUT_NAMES: Final[dict[str, str]] = {
    "adafruit-matrix-bonnet": "AdafruitMatrixBonnet",
    "adafruit-matrix-bonnet-bgr": "AdafruitMatrixBonnetBGR",
    "adafruit-matrix-hat": "AdafruitMatrixHat",
    "adafruit-matrix-hat-bgr": "AdafruitMatrixHatBGR",
}


@dataclass(frozen=True)
class ColorStep:
    name: str
    rgb: tuple[int, int, int]


COLOR_STEPS: Final[tuple[ColorStep, ...]] = (
    ColorStep("red", (255, 0, 0)),
    ColorStep("green", (0, 255, 0)),
    ColorStep("blue", (0, 0, 255)),
)


def main() -> int:
    """Run the Piomatter RGB-cycle sanity test."""

    args = parse_args()
    geometry = piomatter.Geometry(
        width=args.width,
        height=args.height,
        n_addr_lines=args.n_addr_lines,
        rotation=piomatter.Orientation.Normal,
        n_planes=args.n_planes,
        n_temporal_planes=args.n_temporal_planes,
    )
    framebuffer = np.zeros((geometry.height, geometry.width, 3), dtype=np.uint8)
    matrix = piomatter.PioMatter(
        colorspace=piomatter.Colorspace.RGB888Packed,
        pinout=getattr(piomatter.Pinout, PINOUT_NAMES[args.pinout]),
        framebuffer=framebuffer,
        geometry=geometry,
    )

    logger.info(
        "Starting Piomatter RGB cycle: %sx%s pinout=%s n_addr_lines=%s n_planes=%s n_temporal_planes=%s interval=%.3fs hold=%.2fs iterations=%s",
        args.width,
        args.height,
        args.pinout,
        args.n_addr_lines,
        args.n_planes,
        args.n_temporal_planes,
        args.color_interval_seconds,
        args.hold_seconds,
        "infinite" if args.iterations == 0 else args.iterations,
    )

    try:
        run_rgb_cycle(
            matrix=matrix,
            framebuffer=framebuffer,
            hold_seconds=args.hold_seconds,
            color_interval_seconds=args.color_interval_seconds,
            iterations=args.iterations,
            pattern=args.pattern,
        )
    finally:
        del matrix
        gc.collect()
        time.sleep(0.2)
    return 0


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the Piomatter RGB-cycle baseline."""

    parser = argparse.ArgumentParser(
        description="Cycle a Piomatter-backed HUB75 display through red, green, and blue."
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--n-addr-lines", type=int, default=DEFAULT_N_ADDR_LINES)
    parser.add_argument("--n-planes", type=int, default=DEFAULT_N_PLANES)
    parser.add_argument(
        "--n-temporal-planes",
        type=int,
        default=DEFAULT_N_TEMPORAL_PLANES,
    )
    parser.add_argument(
        "--pinout",
        type=str,
        default=DEFAULT_PINOUT,
        choices=PINOUT_CHOICES,
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default=DEFAULT_PATTERN,
        choices=PATTERN_CHOICES,
    )
    parser.add_argument(
        "--color-interval-seconds",
        type=float,
        default=DEFAULT_COLOR_INTERVAL_SECONDS,
    )
    parser.add_argument("--hold-seconds", type=float, default=DEFAULT_HOLD_SECONDS)
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="How many RGB cycles to run. Use 0 to loop until interrupted.",
    )
    return parser.parse_args()


def run_rgb_cycle(
    matrix: piomatter.PioMatter,
    framebuffer: np.ndarray,
    hold_seconds: float,
    color_interval_seconds: float,
    iterations: int,
    pattern: str,
) -> None:
    """Display RGB primaries in sequence for the configured duration."""

    if pattern == "quadrants":
        run_quadrant_scene(
            matrix=matrix,
            framebuffer=framebuffer,
            hold_seconds=hold_seconds,
            iterations=iterations,
        )
        return
    if pattern == "center-box":
        run_center_box_scene(
            matrix=matrix,
            framebuffer=framebuffer,
            hold_seconds=hold_seconds,
            iterations=iterations,
        )
        return

    total_cycles = iterations if iterations > 0 else None
    completed_cycles = 0

    try:
        while total_cycles is None or completed_cycles < total_cycles:
            cycle_start = time.monotonic()
            while time.monotonic() - cycle_start < hold_seconds:
                elapsed = time.monotonic() - cycle_start
                interval_index = int(elapsed / max(color_interval_seconds, 0.001))
                step = COLOR_STEPS[interval_index % len(COLOR_STEPS)]
                fill_framebuffer(framebuffer, step.rgb)
                matrix.show()
                logger.info("Displayed Piomatter %s frame", step.name)
                time.sleep(color_interval_seconds)
            completed_cycles += 1
    except KeyboardInterrupt:
        logger.info("Stopping Piomatter RGB cycle on keyboard interrupt.")


def run_quadrant_scene(
    matrix: piomatter.PioMatter,
    framebuffer: np.ndarray,
    hold_seconds: float,
    iterations: int,
) -> None:
    """Display a static 4-quadrant correctness scene for the configured duration."""

    total_cycles = iterations if iterations > 0 else None
    completed_cycles = 0

    try:
        while total_cycles is None or completed_cycles < total_cycles:
            fill_quadrant_framebuffer(framebuffer)
            matrix.show()
            logger.info("Displayed Piomatter quadrants frame")
            time.sleep(hold_seconds)
            completed_cycles += 1
    except KeyboardInterrupt:
        logger.info("Stopping Piomatter quadrants scene on keyboard interrupt.")


def fill_framebuffer(framebuffer: np.ndarray, rgb: tuple[int, int, int]) -> None:
    """Fill the framebuffer with one solid RGB color."""

    framebuffer[:, :, 0] = rgb[0]
    framebuffer[:, :, 1] = rgb[1]
    framebuffer[:, :, 2] = rgb[2]


def fill_quadrant_framebuffer(framebuffer: np.ndarray) -> None:
    """Fill the framebuffer with red/green/blue/white quadrant blocks."""

    half_height = framebuffer.shape[0] // 2
    half_width = framebuffer.shape[1] // 2
    framebuffer[:half_height, :half_width, :] = (255, 0, 0)
    framebuffer[:half_height, half_width:, :] = (0, 255, 0)
    framebuffer[half_height:, :half_width, :] = (0, 0, 255)
    framebuffer[half_height:, half_width:, :] = (255, 255, 255)


def run_center_box_scene(
    matrix: piomatter.PioMatter,
    framebuffer: np.ndarray,
    hold_seconds: float,
    iterations: int,
) -> None:
    """Display a sparse centered white box scene for the configured duration."""

    total_cycles = iterations if iterations > 0 else None
    completed_cycles = 0

    try:
        while total_cycles is None or completed_cycles < total_cycles:
            fill_center_box_framebuffer(framebuffer)
            matrix.show()
            logger.info("Displayed Piomatter center-box frame")
            time.sleep(hold_seconds)
            completed_cycles += 1
    except KeyboardInterrupt:
        logger.info("Stopping Piomatter center-box scene on keyboard interrupt.")


def fill_center_box_framebuffer(framebuffer: np.ndarray) -> None:
    """Fill the framebuffer with a small centered white box on a black background."""

    box_height = max(4, framebuffer.shape[0] // 4)
    box_width = max(4, framebuffer.shape[1] // 8)
    start_y = (framebuffer.shape[0] - box_height) // 2
    start_x = (framebuffer.shape[1] - box_width) // 2
    framebuffer[:, :, :] = (0, 0, 0)
    framebuffer[start_y : start_y + box_height, start_x : start_x + box_width, :] = (
        255,
        255,
        255,
    )


if __name__ == "__main__":
    raise SystemExit(main())
