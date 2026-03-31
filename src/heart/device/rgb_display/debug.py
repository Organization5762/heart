"""Debug helpers for validating Raspberry Pi 5 HUB75 pin state with pinctrl."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from heart.utilities.logging import get_logger

from .runtime import _load_matrix_runtime_module

logger = get_logger(__name__)

DEFAULT_DEBUG_PANEL_ROWS = 64
DEFAULT_DEBUG_PANEL_COLS = 64
DEFAULT_DEBUG_CHAIN_LENGTH = 1
DEFAULT_DEBUG_PARALLEL = 1
PINCTRL_BINARY = "pinctrl"
PI_MODEL_PATH = Path("/proc/device-tree/model")
PI5_MODEL_TOKEN = "Raspberry Pi 5"
PI5_HAT_PWM_BACKEND_NAME = "pi5-adafruit-hat-pwm"
DEFAULT_PINCTRL_DEBUG_PATTERN = (
    ("oe_pwm", 18, "dh"),
    ("clk", 17, "dl"),
    ("lat", 21, "dh"),
    ("a", 22, "dl"),
    ("b", 26, "dh"),
    ("c", 27, "dl"),
    ("d", 20, "dh"),
    ("e", 24, "dh"),
    ("r1", 5, "dh"),
    ("g1", 13, "dl"),
    ("b1", 6, "dh"),
    ("r2", 12, "dl"),
    ("g2", 16, "dh"),
    ("b2", 23, "dl"),
)


@dataclass(frozen=True)
class MatrixPinctrlDebugSnapshot:
    backend_name: str
    width: int
    height: int
    pin_states_before: dict[int, str]
    pin_states_driven: dict[int, str]
    pin_states_restored: dict[int, str]


def is_supported_pi5_host() -> bool:
    """Return whether the current host is a Raspberry Pi 5 with a readable model file."""

    try:
        return PI5_MODEL_TOKEN in _read_pi_model()
    except FileNotFoundError:
        return False


def run_pi5_pinctrl_debug_probe(
    panel_rows: int = DEFAULT_DEBUG_PANEL_ROWS,
    panel_cols: int = DEFAULT_DEBUG_PANEL_COLS,
    chain_length: int = DEFAULT_DEBUG_CHAIN_LENGTH,
    parallel: int = DEFAULT_DEBUG_PARALLEL,
) -> MatrixPinctrlDebugSnapshot:
    """Drive the Pi 5 HUB75 pin map through pinctrl and capture before/after snapshots."""

    if not is_supported_pi5_host():
        raise RuntimeError("Pi 5 pinctrl debug probe requires a Raspberry Pi 5 host.")

    native_module = _load_matrix_runtime_module()
    config = native_module.MatrixConfig(
        wiring=native_module.WiringProfile.AdafruitHatPwm,
        panel_rows=panel_rows,
        panel_cols=panel_cols,
        chain_length=chain_length,
        parallel=parallel,
        color_order=native_module.ColorOrder.RGB,
    )
    driver = native_module.MatrixDriver(config)
    gpios = tuple(signal_gpio for _signal_name, signal_gpio, _level in DEFAULT_PINCTRL_DEBUG_PATTERN)
    width = driver.width
    height = driver.height

    try:
        stats = driver.stats()
        backend_name = cast(str, stats.backend_name)
        if backend_name != PI5_HAT_PWM_BACKEND_NAME:
            raise RuntimeError(
                "Pi 5 pinctrl debug probe expected the Pi 5 HAT PWM backend "
                f"but received {backend_name!r}."
            )
        pin_states_before = _capture_pinctrl_state(gpios)
        _drive_debug_pattern()
        pin_states_driven = _capture_pinctrl_state(gpios)
    finally:
        _restore_debug_pattern(gpios)
        driver.close()

    pin_states_restored = _capture_pinctrl_state(gpios)
    return MatrixPinctrlDebugSnapshot(
        backend_name=backend_name,
        width=width,
        height=height,
        pin_states_before=pin_states_before,
        pin_states_driven=pin_states_driven,
        pin_states_restored=pin_states_restored,
    )


def main() -> int:
    """Run the Pi 5 pinctrl debug probe and print a JSON snapshot."""

    parser = argparse.ArgumentParser(
        description="Capture a Pi 5 HUB75 pinctrl snapshot for the clean-room runtime."
    )
    parser.add_argument("--panel-rows", type=int, default=DEFAULT_DEBUG_PANEL_ROWS)
    parser.add_argument("--panel-cols", type=int, default=DEFAULT_DEBUG_PANEL_COLS)
    parser.add_argument("--chain-length", type=int, default=DEFAULT_DEBUG_CHAIN_LENGTH)
    parser.add_argument("--parallel", type=int, default=DEFAULT_DEBUG_PARALLEL)
    args = parser.parse_args()

    snapshot = run_pi5_pinctrl_debug_probe(
        panel_rows=args.panel_rows,
        panel_cols=args.panel_cols,
        chain_length=args.chain_length,
        parallel=args.parallel,
    )
    print(json.dumps(asdict(snapshot), indent=2, sort_keys=True))
    return 0


def _capture_pinctrl_state(gpios: tuple[int, ...]) -> dict[int, str]:
    output = _run_command(
        [PINCTRL_BINARY, "get", ",".join(str(gpio) for gpio in gpios)]
    )
    pin_states: dict[int, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        gpio_text, _separator, _rest = line.partition(":")
        pin_states[int(gpio_text.strip())] = line.strip()
    return pin_states


def _drive_debug_pattern() -> None:
    for _signal_name, gpio, level in DEFAULT_PINCTRL_DEBUG_PATTERN:
        _run_command([PINCTRL_BINARY, "set", str(gpio), "op", "pn", level])


def _restore_debug_pattern(gpios: tuple[int, ...]) -> None:
    for gpio in gpios:
        try:
            _run_command([PINCTRL_BINARY, "set", str(gpio), "no", "pn"])
        except (FileNotFoundError, RuntimeError):
            logger.exception("Failed to restore GPIO %s after pinctrl debug probe.", gpio)


def _read_pi_model() -> str:
    return PI_MODEL_PATH.read_text(encoding="utf-8", errors="ignore")


def _run_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(command)!r} failed with exit code {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
