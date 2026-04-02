"""Prepare a Piomatter checkout with a compact row-engine variant and run the RGB cycle demo."""

from __future__ import annotations

import argparse
import shutil
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
DEFAULT_N_PLANES = 10
DEFAULT_N_TEMPORAL_PLANES = 2
DEFAULT_MAX_XFER_BYTES = 262_140
DEFAULT_PINOUT = "adafruit-matrix-bonnet"
DEFAULT_PATTERN = "rgb-cycle"
DEFAULT_RESCALE_MODE = "stock"
DEFAULT_TARGET_FREQ_HZ = 27_000_000
DEFAULT_VARIANT = "row-repeat"
DEFAULT_WIDTH = 64
BEST_KNOWN_VARIANT = "best-known"
PREPARE_SCRIPT = REPO_ROOT / "scripts" / "prepare_piomatter_parity_checkout.py"
RGB_CYCLE_SCRIPT = REPO_ROOT / "scripts" / "piomatter_rgb_cycle.py"
ROW_REPEAT_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_repeat_engine.h"
)
ROW_COMPACT_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_compact_engine.h"
)
ROW_COUNTED_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_counted_engine.h"
)
ROW_HYBRID_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_hybrid_engine.h"
)
ROW_RUNS_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_runs_engine.h"
)
ROW_SPLIT_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_split_engine.h"
)
ROW_WINDOW_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_window_engine.h"
)

def row_repeat_pio_source_path() -> Path:
    candidates = (
        REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_repeat_engine_parity.pio",
        REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_repeat_engine_parity.pio",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def row_compact_pio_source_path() -> Path:
    candidates = (
        REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_compact_engine_parity.pio",
        REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_compact_engine_parity.pio",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def row_compact_tight_pio_source_path() -> Path:
    candidates = (
        REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_compact_tight_engine_parity.pio",
        REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_compact_tight_engine_parity.pio",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def row_hybrid_pio_source_path() -> Path:
    candidates = (
        REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_hybrid_engine_parity.pio",
        REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_hybrid_engine_parity.pio",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def row_counted_pio_source_path() -> Path:
    candidates = (
        REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_counted_engine_parity.pio",
        REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_counted_engine_parity.pio",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def row_runs_pio_source_path() -> Path:
    candidates = (
        REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_runs_engine_parity.pio",
        REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_runs_engine_parity.pio",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def row_split_pio_source_path() -> Path:
    candidates = (
        REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_split_engine_parity.pio",
        REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_split_engine_parity.pio",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def row_window_pio_source_path() -> Path:
    candidates = (
        REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_window_engine_parity.pio",
        REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_window_engine_parity.pio",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optionally patch/reinstall Piomatter with a compact row-engine experiment, then run the RGB cycle demo."
    )
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument("--skip-prepare", action="store_true")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--n-addr-lines", type=int, default=DEFAULT_N_ADDR_LINES)
    parser.add_argument("--n-planes", type=int, default=DEFAULT_N_PLANES)
    parser.add_argument(
        "--n-temporal-planes",
        type=int,
        default=DEFAULT_N_TEMPORAL_PLANES,
    )
    parser.add_argument("--pinout", type=str, default=DEFAULT_PINOUT)
    parser.add_argument("--pattern", type=str, default=DEFAULT_PATTERN)
    parser.add_argument(
        "--variant",
        type=str,
        default=DEFAULT_VARIANT,
        choices=(
            "row-repeat",
            "row-compact",
            "row-compact-tight",
            "row-counted",
            "row-hybrid",
            "row-runs",
            "row-split",
            "row-window",
            BEST_KNOWN_VARIANT,
        ),
    )
    parser.add_argument("--max-xfer-bytes", type=int, default=DEFAULT_MAX_XFER_BYTES)
    parser.add_argument("--target-freq-hz", type=int, default=DEFAULT_TARGET_FREQ_HZ)
    parser.add_argument("--rescale-mode", type=str, default=DEFAULT_RESCALE_MODE)
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
    resolved_variant = resolve_effective_variant(args.variant, args.pattern)
    if resolved_variant == "row-repeat":
        pio_source = row_repeat_pio_source_path()
        render_override = ROW_REPEAT_RENDER_OVERRIDE
    elif resolved_variant == "row-compact":
        pio_source = row_compact_pio_source_path()
        render_override = ROW_COMPACT_RENDER_OVERRIDE
    elif resolved_variant == "row-compact-tight":
        pio_source = row_compact_tight_pio_source_path()
        render_override = ROW_COMPACT_RENDER_OVERRIDE
    elif resolved_variant == "row-counted":
        pio_source = row_counted_pio_source_path()
        render_override = ROW_COUNTED_RENDER_OVERRIDE
    elif resolved_variant == "row-hybrid":
        pio_source = row_hybrid_pio_source_path()
        render_override = ROW_HYBRID_RENDER_OVERRIDE
    elif resolved_variant == "row-runs":
        if args.pattern not in {"rgb-cycle", "quadrants", "center-box"}:
            raise ValueError("row-runs only supports rgb-cycle, quadrants, and center-box patterns")
        pio_source = row_runs_pio_source_path()
        render_override = ROW_RUNS_RENDER_OVERRIDE
    elif resolved_variant == "row-window":
        if args.pattern not in {"rgb-cycle", "quadrants", "center-box"}:
            raise ValueError("row-window only supports rgb-cycle, quadrants, and center-box patterns")
        pio_source = row_window_pio_source_path()
        render_override = ROW_WINDOW_RENDER_OVERRIDE
    else:
        if args.pattern not in {"rgb-cycle", "quadrants"}:
            raise ValueError("row-split only supports rgb-cycle and quadrants patterns")
        pio_source = row_split_pio_source_path()
        render_override = ROW_SPLIT_RENDER_OVERRIDE
    if not args.skip_prepare:
        run_command(
            [
                sys.executable,
                str(PREPARE_SCRIPT),
                "--checkout",
                str(args.checkout),
                "--pio-source",
                str(pio_source),
                "--render-override",
                str(render_override),
                "--target-freq-hz",
                str(args.target_freq_hz),
                "--max-xfer-bytes",
                str(args.max_xfer_bytes),
                "--rescale-mode",
                args.rescale_mode,
            ]
        )
    if not args.skip_install:
        install_command = [sys.executable, "-m", "pip", "install", "--user", "--force-reinstall"]
        if args.break_system_packages:
            install_command.append("--break-system-packages")
        clean_checkout_build_artifacts(args.checkout)
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
            "--n-planes",
            str(args.n_planes),
            "--n-temporal-planes",
            str(args.n_temporal_planes),
            "--pinout",
            args.pinout,
            "--pattern",
            args.pattern,
            "--hold-seconds",
            str(args.hold_seconds),
            "--color-interval-seconds",
            str(args.color_interval_seconds),
            "--iterations",
            str(args.iterations),
        ]
    )
    return 0


def resolve_effective_variant(variant: str, pattern: str) -> str:
    if variant != BEST_KNOWN_VARIANT:
        return variant
    return "row-compact"


def run_command(command: list[str]) -> None:
    LOGGER.info("Running %s", command)
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def clean_checkout_build_artifacts(checkout: Path) -> None:
    for build_path in (checkout / "build", checkout / "dist"):
        if build_path.is_dir():
            shutil.rmtree(build_path, ignore_errors=True)
        elif build_path.exists():
            build_path.unlink(missing_ok=True)
    for egg_info_path in checkout.glob("*.egg-info"):
        if egg_info_path.is_dir():
            shutil.rmtree(egg_info_path, ignore_errors=True)
    for dist_info_path in checkout.glob("*.dist-info"):
        if dist_info_path.is_dir():
            shutil.rmtree(dist_info_path, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
