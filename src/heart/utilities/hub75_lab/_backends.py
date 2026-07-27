"""Internal implementations for retained visual HUB75 experiments."""

from __future__ import annotations

import argparse
import math
import time
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, cast, final

from PIL import Image
from typing_extensions import override

from heart.device.rgb_display.runtime import _load_matrix_runtime_module
from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import

LOGGER = get_logger(__name__)
lgpio = cast(ModuleType | None, optional_import("lgpio", logger=LOGGER))
rpi_gpio = cast(ModuleType | None, optional_import("RPi.GPIO", logger=LOGGER))

RGBA_IMAGE_MODE = "RGBA"
ALPHA_OPAQUE = 255
KERNEL_LOOP_BACKEND_TOKEN = "kernel-loop"
WIRING_PROFILE_NAMES = {
    "adafruit-hat": "AdafruitHat",
    "adafruit-hat-pwm": "AdafruitHatPwm",
}
GPIO_DIAGNOSTIC_MODES = ("scan", "hold-row", "latch-pulse", "walking-bit")
RGB_GPIOS = (5, 13, 6, 12, 16, 23)
ADDRESS_GPIOS = (22, 26, 27, 20, 24)
CLK_GPIO = 17
LAT_GPIO = 21
OE_GPIO = 18
LEGACY_OE_GPIO = 4
CONTROL_GPIOS = (CLK_GPIO, LAT_GPIO, OE_GPIO, LEGACY_OE_GPIO)
ALL_GPIOS = RGB_GPIOS + ADDRESS_GPIOS + CONTROL_GPIOS


def main() -> int:
    """Run one internal experiment implementation."""

    args = _parse_args()
    if args.experiment == "gpio-smoke":
        _run_gpio_smoke(args)
    else:
        _run_runtime_experiment(args)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Internal backend for scripts/hub75_experiment.py. "
            "Use the public runner for documented experiments."
        )
    )
    parser.add_argument(
        "experiment",
        choices=(
            "runtime-color-cycle",
            "runtime-gradient",
            "runtime-single-line",
            "gpio-smoke",
        ),
    )
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--cols", type=int, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--chain-length", type=int, default=1)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument(
        "--hardware-mapping",
        choices=tuple(WIRING_PROFILE_NAMES),
        default="adafruit-hat-pwm",
    )
    parser.add_argument("--led-rgb-sequence", default="RGB")
    parser.add_argument("--intensities", default="32,96,160,255")
    parser.add_argument("--row-index", type=int, default=0)
    parser.add_argument("--line-thickness", type=int, default=1)
    parser.add_argument("--red", type=int, default=255)
    parser.add_argument("--green", type=int, default=255)
    parser.add_argument("--blue", type=int, default=255)
    parser.add_argument("--row-dwell-seconds", type=float, default=0.0005)
    parser.add_argument(
        "--gpio-diagnostic-mode",
        choices=GPIO_DIAGNOSTIC_MODES,
        default="scan",
    )
    return parser.parse_args()


def _run_runtime_experiment(args: argparse.Namespace) -> None:
    matrix = _build_matrix(args)
    try:
        if args.experiment == "runtime-color-cycle":
            _run_color_cycle(matrix, args.intensities, args.seconds)
        elif args.experiment == "runtime-gradient":
            _run_gradient(matrix, args.seconds)
        elif args.experiment == "runtime-single-line":
            _run_single_line(
                matrix,
                seconds=args.seconds,
                row_index=args.row_index,
                thickness=args.line_thickness,
                color=(args.red, args.green, args.blue),
            )
        else:  # pragma: no cover - argparse guards choices
            raise ValueError(f"unsupported runtime experiment: {args.experiment}")
    except KeyboardInterrupt:
        LOGGER.info("Stopping HUB75 experiment on keyboard interrupt.")
    finally:
        matrix.close()


def _build_matrix(args: argparse.Namespace) -> Any:
    native_module = _load_matrix_runtime_module()
    config = native_module.MatrixConfig(
        wiring=getattr(
            native_module.WiringProfile,
            WIRING_PROFILE_NAMES[args.hardware_mapping],
        ),
        panel_rows=args.rows,
        panel_cols=args.cols,
        chain_length=args.chain_length,
        parallel=args.parallel,
        color_order=getattr(
            native_module.ColorOrder,
            args.led_rgb_sequence.upper(),
        ),
    )
    return native_module.MatrixDriver(config)


def _run_color_cycle(matrix: Any, raw_intensities: str, seconds: float) -> None:
    intensities = tuple(
        int(component.strip())
        for component in raw_intensities.split(",")
        if component.strip()
    )
    if not intensities or any(value < 0 or value > 255 for value in intensities):
        raise ValueError("intensities must contain comma-separated values in [0, 255]")

    colors = (
        ("red", lambda value: (value, 0, 0, ALPHA_OPAQUE)),
        ("green", lambda value: (0, value, 0, ALPHA_OPAQUE)),
        ("blue", lambda value: (0, 0, value, ALPHA_OPAQUE)),
    )
    persistent_refresh = KERNEL_LOOP_BACKEND_TOKEN in _backend_name(matrix)
    for intensity in intensities:
        for name, build_rgba in colors:
            image = Image.new(
                RGBA_IMAGE_MODE,
                (matrix.width, matrix.height),
                color=build_rgba(intensity),
            )
            frame = image.tobytes()
            deadline = time.monotonic() + seconds
            submit_count = 0
            while True:
                matrix.submit_rgba(frame, matrix.width, matrix.height)
                submit_count += 1
                if persistent_refresh or time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
            if persistent_refresh:
                time.sleep(seconds)
            LOGGER.info(
                "Displayed %s intensity=%s submits=%s seconds=%.3f backend=%s",
                name,
                intensity,
                submit_count,
                seconds,
                _backend_name(matrix),
            )


def _run_gradient(matrix: Any, seconds: float) -> None:
    started = time.monotonic()
    deadline = started + seconds
    frame_count = 0
    while time.monotonic() < deadline:
        phase = (time.monotonic() - started) / 8.0
        image = Image.new(
            RGBA_IMAGE_MODE,
            (matrix.width, matrix.height),
            color=(0, 0, 0, ALPHA_OPAQUE),
        )
        phase_offset = 0.5 + 0.5 * math.sin(phase * math.tau)
        max_column = max(matrix.width - 1, 1)
        for column in range(matrix.width):
            column_mix = column / max_column
            red = _clamp_u8(int(32 + 120 * (column_mix + phase_offset) / 2.0))
            blue = _clamp_u8(
                int(96 + (1.0 - column_mix) * 120 - phase_offset * 48)
            )
            green = _clamp_u8(
                int(40 + (1.0 - abs(column_mix - 0.5) * 2.0) * 24)
            )
            for row in range(matrix.height):
                image.putpixel(
                    (column, row),
                    (red, green, blue, ALPHA_OPAQUE),
                )
        matrix.submit_rgba(image.tobytes(), matrix.width, matrix.height)
        frame_count += 1
        time.sleep(0.05)
    LOGGER.info("Displayed %s gradient frames over %.3fs", frame_count, seconds)


def _run_single_line(
    matrix: Any,
    *,
    seconds: float,
    row_index: int,
    thickness: int,
    color: tuple[int, int, int],
) -> None:
    if row_index < 0 or thickness <= 0 or row_index + thickness > matrix.height:
        raise ValueError("single-line row and thickness must fit inside the display")
    image = Image.new(
        RGBA_IMAGE_MODE,
        (matrix.width, matrix.height),
        color=(0, 0, 0, ALPHA_OPAQUE),
    )
    for row in range(row_index, row_index + thickness):
        for column in range(matrix.width):
            image.putpixel((column, row), (*color, ALPHA_OPAQUE))
    frame = image.tobytes()
    deadline = time.monotonic() + seconds
    submit_count = 0
    while True:
        matrix.submit_rgba(frame, matrix.width, matrix.height)
        submit_count += 1
        if time.monotonic() >= deadline:
            break
    LOGGER.info(
        "Displayed line row=%s thickness=%s color=%s submits=%s seconds=%.3f",
        row_index,
        thickness,
        color,
        submit_count,
        seconds,
    )


def _run_gpio_smoke(args: argparse.Namespace) -> None:
    gpio = _build_gpio_backend()
    _configure_gpio(gpio)
    step = GpioColorStep(
        top_rgb=(args.red >= 128, args.green >= 128, args.blue >= 128),
        bottom_rgb=(args.red >= 128, args.green >= 128, args.blue >= 128),
    )
    deadline = time.monotonic() + args.seconds
    try:
        if args.gpio_diagnostic_mode in ("scan", "hold-row"):
            _gpio_scan(
                gpio,
                rows=args.rows,
                cols=args.cols,
                row_index=(
                    None if args.gpio_diagnostic_mode == "scan" else args.row_index
                ),
                step=step,
                deadline=deadline,
                row_dwell_seconds=args.row_dwell_seconds,
            )
        elif args.gpio_diagnostic_mode == "latch-pulse":
            _gpio_latch_pulse(gpio, args, step, deadline)
        elif args.gpio_diagnostic_mode == "walking-bit":
            _gpio_walking_bit(gpio, args, deadline)
        else:  # pragma: no cover - argparse guards choices
            raise ValueError(args.gpio_diagnostic_mode)
    except KeyboardInterrupt:
        LOGGER.info("Stopping GPIO smoke test on keyboard interrupt.")
    finally:
        _blank_panel(gpio)
        gpio.cleanup()


def _gpio_scan(
    gpio: GpioBackend,
    *,
    rows: int,
    cols: int,
    row_index: int | None,
    step: GpioColorStep,
    deadline: float,
    row_dwell_seconds: float,
) -> None:
    row_pairs = rows // 2
    if row_index is not None and (row_index < 0 or row_index >= row_pairs):
        raise ValueError(f"row_index must be in [0, {row_pairs - 1}]")
    indices = range(row_pairs) if row_index is None else (row_index,)
    while time.monotonic() < deadline:
        for row_pair in indices:
            _write_oe(gpio, enabled=False)
            _set_row_address(gpio, row_pair)
            _shift_constant_row(gpio, cols, step)
            _latch(gpio)
            _write_oe(gpio, enabled=True)
            time.sleep(row_dwell_seconds)


def _gpio_latch_pulse(
    gpio: GpioBackend,
    args: argparse.Namespace,
    step: GpioColorStep,
    deadline: float,
) -> None:
    _write_oe(gpio, enabled=False)
    _set_row_address(gpio, args.row_index)
    _shift_constant_row(gpio, args.cols, step)
    _latch(gpio)
    _write_oe(gpio, enabled=True)
    while time.monotonic() < deadline:
        time.sleep(args.row_dwell_seconds)
        _latch(gpio)


def _gpio_walking_bit(
    gpio: GpioBackend,
    args: argparse.Namespace,
    deadline: float,
) -> None:
    while time.monotonic() < deadline:
        for lit_column in range(args.cols):
            if time.monotonic() >= deadline:
                break
            _write_oe(gpio, enabled=False)
            _set_row_address(gpio, args.row_index)
            for column in range(args.cols):
                lit = column == lit_column
                _write_rgb(
                    gpio,
                    GpioColorStep(
                        top_rgb=(lit, False, False),
                        bottom_rgb=(False, False, False),
                    ),
                )
                gpio.output(CLK_GPIO, gpio.HIGH)
                gpio.output(CLK_GPIO, gpio.LOW)
            _latch(gpio)
            _write_oe(gpio, enabled=True)
            time.sleep(args.row_dwell_seconds)


def _configure_gpio(gpio: GpioBackend) -> None:
    for pin in ALL_GPIOS:
        gpio.setup_output(pin, initial=gpio.LOW)
    _write_oe(gpio, enabled=False)
    gpio.output(LAT_GPIO, gpio.LOW)
    gpio.output(CLK_GPIO, gpio.LOW)


def _blank_panel(gpio: GpioBackend) -> None:
    _write_oe(gpio, enabled=False)
    gpio.output(LAT_GPIO, gpio.LOW)
    gpio.output(CLK_GPIO, gpio.LOW)
    for pin in RGB_GPIOS + ADDRESS_GPIOS:
        gpio.output(pin, gpio.LOW)


def _write_oe(gpio: GpioBackend, *, enabled: bool) -> None:
    level = gpio.LOW if enabled else gpio.HIGH
    gpio.output(OE_GPIO, level)
    gpio.output(LEGACY_OE_GPIO, level)


def _set_row_address(gpio: GpioBackend, row_pair: int) -> None:
    for bit_index, pin in enumerate(ADDRESS_GPIOS):
        gpio.output(pin, gpio.HIGH if row_pair & (1 << bit_index) else gpio.LOW)


def _shift_constant_row(
    gpio: GpioBackend,
    cols: int,
    step: GpioColorStep,
) -> None:
    for _column in range(cols):
        _write_rgb(gpio, step)
        gpio.output(CLK_GPIO, gpio.HIGH)
        gpio.output(CLK_GPIO, gpio.LOW)


def _write_rgb(gpio: GpioBackend, step: GpioColorStep) -> None:
    for pin, enabled in zip(
        RGB_GPIOS,
        (*step.top_rgb, *step.bottom_rgb),
        strict=True,
    ):
        gpio.output(pin, gpio.HIGH if enabled else gpio.LOW)


def _latch(gpio: GpioBackend) -> None:
    gpio.output(LAT_GPIO, gpio.HIGH)
    gpio.output(LAT_GPIO, gpio.LOW)


def _build_gpio_backend() -> GpioBackend:
    return _select_gpio_backend(
        LgpioBackend if lgpio is not None else None,
        RpiGpioBackend if rpi_gpio is not None else None,
    )


def _select_gpio_backend(
    lgpio_factory: Callable[[], GpioBackend] | None,
    rpi_gpio_factory: Callable[[], GpioBackend] | None,
) -> GpioBackend:
    if lgpio_factory is not None:
        try:
            backend = lgpio_factory()
        except Exception as error:
            LOGGER.warning(
                "lgpio backend unavailable for HUB75 GPIO smoke test: %s",
                error,
            )
        else:
            LOGGER.info("Using lgpio backend for HUB75 GPIO smoke test.")
            return backend
    if rpi_gpio_factory is not None:
        LOGGER.info("Using RPi.GPIO backend for HUB75 GPIO smoke test.")
        return rpi_gpio_factory()
    raise RuntimeError("No usable GPIO backend found for HUB75 GPIO smoke test")


def _backend_name(matrix: Any) -> str:
    return str(matrix.stats().backend_name)


def _clamp_u8(value: int) -> int:
    return max(0, min(255, value))


@final
@dataclass(frozen=True)
class GpioColorStep:
    top_rgb: tuple[bool, bool, bool]
    bottom_rgb: tuple[bool, bool, bool]


class GpioBackend:
    """Narrow GPIO contract needed by the direct smoke test."""

    HIGH = 1
    LOW = 0

    def setup_output(self, gpio: int, *, initial: int) -> None:
        raise NotImplementedError

    def output(self, gpio: int, value: int) -> None:
        raise NotImplementedError

    def cleanup(self) -> None:
        raise NotImplementedError


@final
class LgpioBackend(GpioBackend):
    """Pi 5 lgpio implementation."""

    def __init__(self) -> None:
        if lgpio is None:  # pragma: no cover - constructor boundary
            raise RuntimeError("lgpio is unavailable")
        self._handle = lgpio.gpiochip_open(0)

    @override
    def setup_output(self, gpio: int, *, initial: int) -> None:
        if lgpio is None:  # pragma: no cover - constructor boundary
            raise RuntimeError("lgpio is unavailable")
        lgpio.gpio_claim_output(self._handle, gpio, initial)

    @override
    def output(self, gpio: int, value: int) -> None:
        if lgpio is None:  # pragma: no cover - constructor boundary
            raise RuntimeError("lgpio is unavailable")
        lgpio.gpio_write(self._handle, gpio, value)

    @override
    def cleanup(self) -> None:
        if lgpio is None:  # pragma: no cover - constructor boundary
            raise RuntimeError("lgpio is unavailable")
        lgpio.gpiochip_close(self._handle)


@final
class RpiGpioBackend(GpioBackend):
    """RPi.GPIO compatibility implementation."""

    def __init__(self) -> None:
        if rpi_gpio is None:  # pragma: no cover - constructor boundary
            raise RuntimeError("RPi.GPIO is unavailable")
        rpi_gpio.setwarnings(False)
        rpi_gpio.setmode(rpi_gpio.BCM)

    @override
    def setup_output(self, gpio: int, *, initial: int) -> None:
        if rpi_gpio is None:  # pragma: no cover - constructor boundary
            raise RuntimeError("RPi.GPIO is unavailable")
        rpi_gpio.setup(gpio, rpi_gpio.OUT, initial=initial)

    @override
    def output(self, gpio: int, value: int) -> None:
        if rpi_gpio is None:  # pragma: no cover - constructor boundary
            raise RuntimeError("RPi.GPIO is unavailable")
        rpi_gpio.output(gpio, value)

    @override
    def cleanup(self) -> None:
        if rpi_gpio is None:  # pragma: no cover - constructor boundary
            raise RuntimeError("RPi.GPIO is unavailable")
        rpi_gpio.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
