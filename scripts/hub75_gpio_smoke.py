"""Direct GPIO HUB75 smoke test for Raspberry Pi bring-up.

This intentionally bypasses the heart_rgb_matrix_driver Pi 5 transport and bit-bangs the
bonnet pinout directly through a basic GPIO library. The goal is not performance or low
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

from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class GpioBackend:
    """Minimal GPIO surface shared by the smoke test across Pi GPIO libraries."""

    HIGH = 1
    LOW = 0
    OUT = "out"

    def setup_output(self, gpio: int, *, initial: int) -> None:
        """Configure one GPIO for output with an initial value."""

    def output(self, gpio: int, value: int) -> None:
        """Write one GPIO output value."""

    def cleanup(self) -> None:
        """Release any GPIO state held by the backend."""


class LgpioBackend(GpioBackend):
    """Use lgpio on Pi 5 where RPi.GPIO often fails to detect the SoC base address."""

    def __init__(self) -> None:
        import lgpio

        self._lgpio = lgpio
        self._handle = lgpio.gpiochip_open(0)

    def setup_output(self, gpio: int, *, initial: int) -> None:
        self._lgpio.gpio_claim_output(self._handle, gpio, initial)

    def output(self, gpio: int, value: int) -> None:
        self._lgpio.gpio_write(self._handle, gpio, value)

    def cleanup(self) -> None:
        self._lgpio.gpiochip_close(self._handle)


class RpiGpioBackend(GpioBackend):
    """Fallback backend for environments where RPi.GPIO still works."""

    OUT = None

    def __init__(self) -> None:
        import RPi.GPIO as gpio

        self._gpio = gpio
        self.OUT = gpio.OUT
        self.HIGH = gpio.HIGH
        self.LOW = gpio.LOW
        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)

    def setup_output(self, gpio: int, *, initial: int) -> None:
        self._gpio.setup(gpio, self.OUT, initial=initial)

    def output(self, gpio: int, value: int) -> None:
        self._gpio.output(gpio, value)

    def cleanup(self) -> None:
        self._gpio.cleanup()

DEFAULT_PANEL_ROWS: Final[int] = 64
DEFAULT_PANEL_COLS: Final[int] = 64
DEFAULT_FRAME_HOLD_SECONDS: Final[float] = 3.0
DEFAULT_ROW_DWELL_SECONDS: Final[float] = 0.0005
DEFAULT_ITERATIONS: Final[int] = 0
DEFAULT_INTENSITY: Final[int] = 255
DEFAULT_SINGLE_COLOR: Final[str | None] = None
DEFAULT_SINGLE_ROW_INDEX: Final[int | None] = None
DEFAULT_DIAGNOSTIC_MODE: Final[str] = "scan"
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
LEGACY_OE_SYNC_GPIO: Final[int] = 4

RGB_GPIOS: Final[tuple[int, ...]] = (
    R1_GPIO,
    G1_GPIO,
    B1_GPIO,
    R2_GPIO,
    G2_GPIO,
    B2_GPIO,
)
ADDR_GPIOS: Final[tuple[int, ...]] = (A_GPIO, B_GPIO, C_GPIO, D_GPIO, E_GPIO)
CONTROL_GPIOS: Final[tuple[int, ...]] = (CLK_GPIO, LAT_GPIO, OE_GPIO, LEGACY_OE_SYNC_GPIO)
ALL_GPIOS: Final[tuple[int, ...]] = RGB_GPIOS + ADDR_GPIOS + CONTROL_GPIOS


@dataclass(frozen=True)
class ColorStep:
    name: str
    top_rgb: tuple[bool, bool, bool]
    bottom_rgb: tuple[bool, bool, bool]


def build_gpio_backend() -> GpioBackend:
    """Prefer lgpio on Pi 5 and keep RPi.GPIO only as a compatibility fallback."""

    try:
        backend = LgpioBackend()
        logger.info("Using lgpio backend for HUB75 GPIO smoke test.")
        return backend
    except Exception as error:
        logger.warning("lgpio backend unavailable for HUB75 GPIO smoke test: %s", error)
    try:
        backend = RpiGpioBackend()
        logger.info("Using RPi.GPIO backend for HUB75 GPIO smoke test.")
        return backend
    except Exception as error:
        raise RuntimeError("No usable GPIO backend found for HUB75 GPIO smoke test.") from error


def main() -> int:
    """Run the direct GPIO HUB75 smoke test."""

    args = parse_args()
    color_steps = build_color_steps(args.intensity, args.single_color)
    gpio = build_gpio_backend()
    configure_gpio(gpio)

    logger.info(
        "Starting direct GPIO HUB75 smoke test: mode=%s rows=%s cols=%s hold=%.2fs row_dwell=%.6fs iterations=%s",
        args.diagnostic_mode,
        args.rows,
        args.cols,
        args.frame_hold_seconds,
        args.row_dwell_seconds,
        "infinite" if args.iterations == 0 else args.iterations,
    )

    try:
        if args.diagnostic_mode == "scan":
            run_color_cycle(
                gpio=gpio,
                panel_rows=args.rows,
                panel_cols=args.cols,
                color_steps=color_steps,
                frame_hold_seconds=args.frame_hold_seconds,
                row_dwell_seconds=args.row_dwell_seconds,
                iterations=args.iterations,
                single_row_index=args.single_row_index,
            )
        else:
            run_diagnostic_mode(
                gpio=gpio,
                panel_rows=args.rows,
                panel_cols=args.cols,
                color_steps=color_steps,
                frame_hold_seconds=args.frame_hold_seconds,
                row_dwell_seconds=args.row_dwell_seconds,
                iterations=args.iterations,
                single_row_index=args.single_row_index,
                diagnostic_mode=args.diagnostic_mode,
            )
    except KeyboardInterrupt:
        logger.info("Stopping direct GPIO HUB75 smoke test on keyboard interrupt.")
    finally:
        blank_panel(gpio)
        gpio.cleanup()

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
    parser.add_argument(
        "--single-row-index",
        type=int,
        default=DEFAULT_SINGLE_ROW_INDEX,
        help="If set, repeatedly drive only one row-pair address instead of scanning the full panel.",
    )
    parser.add_argument(
        "--diagnostic-mode",
        choices=("scan", "hold-row", "latch-pulse", "oe-toggle", "walking-bit"),
        default=DEFAULT_DIAGNOSTIC_MODE,
        help="Low-level panel diagnostic mode.",
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


def configure_gpio(gpio: GpioBackend) -> None:
    """Initialize GPIO outputs in a conservative blanked state."""

    for pin in ALL_GPIOS:
        gpio.setup_output(pin, initial=gpio.LOW)
    gpio.output(OE_GPIO, gpio.HIGH)
    gpio.output(LEGACY_OE_SYNC_GPIO, gpio.HIGH)
    gpio.output(LAT_GPIO, gpio.LOW)
    gpio.output(CLK_GPIO, gpio.LOW)


def write_oe(gpio: GpioBackend, enabled: bool) -> None:
    """Drive the primary and legacy PWM-bonnet OE pins in sync."""

    level = gpio.LOW if enabled else gpio.HIGH
    gpio.output(OE_GPIO, level)
    gpio.output(LEGACY_OE_SYNC_GPIO, level)


def run_color_cycle(
    gpio: GpioBackend,
    panel_rows: int,
    panel_cols: int,
    color_steps: tuple[ColorStep, ...],
    frame_hold_seconds: float,
    row_dwell_seconds: float,
    iterations: int,
    single_row_index: int | None,
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
                scan_frame(
                    gpio,
                    row_pairs,
                    panel_cols,
                    step,
                    row_dwell_seconds,
                    single_row_index=single_row_index,
                )
        completed_cycles += 1


def scan_frame(
    gpio: GpioBackend,
    row_pairs: int,
    panel_cols: int,
    step: ColorStep,
    row_dwell_seconds: float,
    *,
    single_row_index: int | None = None,
) -> None:
    """Scan one full frame worth of row pairs for the current solid color."""

    if single_row_index is None:
        row_pair_indices = range(row_pairs)
    else:
        if single_row_index < 0 or single_row_index >= row_pairs:
            raise ValueError(
                f"single_row_index must be in [0, {row_pairs - 1}], got {single_row_index}"
            )
        row_pair_indices = (single_row_index,)

    for row_pair in row_pair_indices:
        write_oe(gpio, enabled=False)
        set_row_address(gpio, row_pair)
        shift_row(gpio, panel_cols, step)
        latch_row(gpio)
        write_oe(gpio, enabled=True)
        time.sleep(row_dwell_seconds)


def set_row_address(gpio: GpioBackend, row_pair: int) -> None:
    """Drive the A..E row-address pins for the requested row pair."""

    for bit_index, pin in enumerate(ADDR_GPIOS):
        pin_value = gpio.HIGH if (row_pair & (1 << bit_index)) else gpio.LOW
        gpio.output(pin, pin_value)


def shift_row(gpio: GpioBackend, panel_cols: int, step: ColorStep) -> None:
    """Shift one row-pair worth of constant RGB data into the panel."""

    for _column in range(panel_cols):
        write_rgb(gpio, step)
        gpio.output(CLK_GPIO, gpio.HIGH)
        gpio.output(CLK_GPIO, gpio.LOW)


def write_rgb(gpio: GpioBackend, step: ColorStep) -> None:
    """Drive the HUB75 RGB data pins for one shifted column."""

    top_red, top_green, top_blue = step.top_rgb
    bottom_red, bottom_green, bottom_blue = step.bottom_rgb
    gpio.output(R1_GPIO, gpio.HIGH if top_red else gpio.LOW)
    gpio.output(G1_GPIO, gpio.HIGH if top_green else gpio.LOW)
    gpio.output(B1_GPIO, gpio.HIGH if top_blue else gpio.LOW)
    gpio.output(R2_GPIO, gpio.HIGH if bottom_red else gpio.LOW)
    gpio.output(G2_GPIO, gpio.HIGH if bottom_green else gpio.LOW)
    gpio.output(B2_GPIO, gpio.HIGH if bottom_blue else gpio.LOW)


def latch_row(gpio: GpioBackend) -> None:
    """Pulse LAT once after a full row's worth of columns have been shifted."""

    gpio.output(LAT_GPIO, gpio.HIGH)
    gpio.output(LAT_GPIO, gpio.LOW)


def blank_panel(gpio: GpioBackend) -> None:
    """Leave the panel in a safe blanked state when the script exits."""

    write_oe(gpio, enabled=False)
    gpio.output(LAT_GPIO, gpio.LOW)
    gpio.output(CLK_GPIO, gpio.LOW)
    for pin in RGB_GPIOS + ADDR_GPIOS:
        gpio.output(pin, gpio.LOW)


def resolve_row_pair_index(panel_rows: int, single_row_index: int | None) -> int:
    """Resolve one valid row-pair index for focused diagnostics."""

    row_pairs = panel_rows // 2
    if single_row_index is None:
        return 0
    if single_row_index < 0 or single_row_index >= row_pairs:
        raise ValueError(f"single_row_index must be in [0, {row_pairs - 1}], got {single_row_index}")
    return single_row_index


def run_diagnostic_mode(
    gpio: GpioBackend,
    panel_rows: int,
    panel_cols: int,
    color_steps: tuple[ColorStep, ...],
    frame_hold_seconds: float,
    row_dwell_seconds: float,
    iterations: int,
    single_row_index: int | None,
    diagnostic_mode: str,
) -> None:
    """Run a focused low-level panel diagnostic."""

    total_cycles = iterations if iterations > 0 else None
    completed_cycles = 0
    row_pair = resolve_row_pair_index(panel_rows, single_row_index)
    step = color_steps[0]

    while total_cycles is None or completed_cycles < total_cycles:
        logger.info("Running diagnostic mode %s on row_pair=%s", diagnostic_mode, row_pair)
        deadline = time.monotonic() + frame_hold_seconds
        if diagnostic_mode == "hold-row":
            run_hold_row(gpio, row_pair, panel_cols, step, deadline, row_dwell_seconds)
        elif diagnostic_mode == "latch-pulse":
            run_latch_pulse(gpio, row_pair, panel_cols, step, deadline, row_dwell_seconds)
        elif diagnostic_mode == "oe-toggle":
            run_oe_toggle(gpio, row_pair, panel_cols, step, deadline, row_dwell_seconds)
        elif diagnostic_mode == "walking-bit":
            run_walking_bit(gpio, row_pair, panel_cols, deadline, row_dwell_seconds)
        else:
            raise ValueError(f"Unsupported diagnostic mode: {diagnostic_mode}")
        completed_cycles += 1


def run_hold_row(
    gpio: GpioBackend,
    row_pair: int,
    panel_cols: int,
    step: ColorStep,
    deadline: float,
    row_dwell_seconds: float,
) -> None:
    """Continuously relatch one solid row-pair and hold it visible."""

    while time.monotonic() < deadline:
        write_oe(gpio, enabled=False)
        set_row_address(gpio, row_pair)
        shift_row(gpio, panel_cols, step)
        latch_row(gpio)
        write_oe(gpio, enabled=True)
        time.sleep(row_dwell_seconds)


def run_latch_pulse(
    gpio: GpioBackend,
    row_pair: int,
    panel_cols: int,
    step: ColorStep,
    deadline: float,
    row_dwell_seconds: float,
) -> None:
    """Latch one solid row-pair once, then repulse LAT only."""

    write_oe(gpio, enabled=False)
    set_row_address(gpio, row_pair)
    shift_row(gpio, panel_cols, step)
    latch_row(gpio)
    write_oe(gpio, enabled=True)
    while time.monotonic() < deadline:
        time.sleep(row_dwell_seconds)
        latch_row(gpio)


def run_oe_toggle(
    gpio: GpioBackend,
    row_pair: int,
    panel_cols: int,
    step: ColorStep,
    deadline: float,
    row_dwell_seconds: float,
) -> None:
    """Latch one solid row-pair once, then toggle OE only."""

    write_oe(gpio, enabled=False)
    set_row_address(gpio, row_pair)
    shift_row(gpio, panel_cols, step)
    latch_row(gpio)
    visible = False
    while time.monotonic() < deadline:
        visible = not visible
        write_oe(gpio, enabled=visible)
        time.sleep(row_dwell_seconds)


def run_walking_bit(
    gpio: GpioBackend,
    row_pair: int,
    panel_cols: int,
    deadline: float,
    row_dwell_seconds: float,
) -> None:
    """Shift a single red pixel across one row-pair repeatedly."""

    while time.monotonic() < deadline:
        for lit_column in range(panel_cols):
            if time.monotonic() >= deadline:
                break
            write_oe(gpio, enabled=False)
            set_row_address(gpio, row_pair)
            for column in range(panel_cols):
                lit = column == lit_column
                write_rgb(
                    gpio,
                    ColorStep("walking-red", (lit, False, False), (False, False, False)),
                )
                gpio.output(CLK_GPIO, gpio.HIGH)
                gpio.output(CLK_GPIO, gpio.LOW)
            latch_row(gpio)
            write_oe(gpio, enabled=True)
            time.sleep(row_dwell_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
