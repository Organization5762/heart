"""Benchmark stock Piomatter versus compact row-engine variants on static test patterns."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from heart.utilities.logging import get_logger

LOGGER = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKOUT = Path("/home/michael/tmp/Adafruit_Blinka_Raspberry_Pi5_Piomatter")
DEFAULT_DURATION_SECONDS = 5.0
DEFAULT_ENABLE_BASELINE_GROUP = True
DEFAULT_BENCHMARK_ATTEMPTS = 2
DEFAULT_BENCHMARK_RETRY_DELAY_SECONDS = 1.0
DEFAULT_BASELINE_VARIANT = "row-compact"
DEFAULT_BASELINE_DRIFT_TOLERANCE = 0.05
DEFAULT_BUILD_CFLAGS = "-O2 -g0"
DEFAULT_BUILD_CXXFLAGS = "-O2 -g0"
DEFAULT_HEIGHT = 64
DEFAULT_INSTALL_SETTLE_SECONDS = 1.0
DEFAULT_MAX_XFER_BYTES = 262_140
DEFAULT_N_ADDR_LINES = 5
DEFAULT_N_PLANES = 10
DEFAULT_N_TEMPORAL_PLANES = 2
DEFAULT_PINOUT = "adafruit-matrix-bonnet"
DEFAULT_PATTERN = "solid-red"
DEFAULT_POST_ADDR_DELAY = 5
DEFAULT_POST_LATCH_DELAY = 0
DEFAULT_POST_OE_DELAY = 0
DEFAULT_POST_MATRIX_DESTROY_SECONDS = 1.0
DEFAULT_SHIFT_ONLY_PLAUSIBILITY_MARGIN = 1.05
DEFAULT_RESCALE_MODE = "stock"
DEFAULT_SLAB_COPIES = "1,4,8,16"
DEFAULT_TARGET_FREQ_HZ = 27_000_000
DEFAULT_VARIANT = "all"
DEFAULT_WARMUP_SECONDS = 1.0
DEFAULT_WIDTH = 64
DEFAULT_RP1_PIO_PARAM_ROOT = Path("/sys/module/rp1_pio/parameters")
DEFAULT_BASELINE_RP1_PIO_PARAMS = ("tx_mmio_blind=Y",)
DEFAULT_EXPERIMENT_RP1_PIO_PARAMS = ("tx_mmio_blind=Y",)
PINOUT_CHOICES = (
    "adafruit-matrix-bonnet",
    "adafruit-matrix-bonnet-bgr",
    "adafruit-matrix-hat",
    "adafruit-matrix-hat-bgr",
)
PATTERN_CHOICES = ("solid-red", "quadrants", "center-box")
BEST_KNOWN_VARIANT = "best-known"
VARIANT_CHOICES = (
    "stock",
    "row-repeat",
    "row-compact",
    "row-compact-tight",
    "row-counted",
    "row-hybrid",
    "row-runs",
    "row-split",
    "row-window",
    BEST_KNOWN_VARIANT,
    "both",
    "all",
)
BASELINE_VARIANT_CHOICES = (
    "stock",
    "row-repeat",
    "row-compact",
    "row-compact-tight",
    "row-counted",
    "row-hybrid",
    "row-runs",
    "row-split",
    "row-window",
)
RESCALE_MODE_CHOICES = ("stock", "none")
PINOUT_NAMES = {
    "adafruit-matrix-bonnet": "AdafruitMatrixBonnet",
    "adafruit-matrix-bonnet-bgr": "AdafruitMatrixBonnetBGR",
    "adafruit-matrix-hat": "AdafruitMatrixHat",
    "adafruit-matrix-hat-bgr": "AdafruitMatrixHatBGR",
}
PREPARE_SCRIPT = REPO_ROOT / "scripts" / "prepare_piomatter_parity_checkout.py"
ROW_REPEAT_PIO_SOURCE_CANDIDATES = (
    REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_repeat_engine_parity.pio",
    REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_repeat_engine_parity.pio",
)
ROW_REPEAT_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_repeat_engine.h"
)
ROW_COMPACT_PIO_SOURCE_CANDIDATES = (
    REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_compact_engine_parity.pio",
    REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_compact_engine_parity.pio",
)
ROW_COMPACT_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_compact_engine.h"
)
ROW_COMPACT_TIGHT_PIO_SOURCE_CANDIDATES = (
    REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_compact_tight_engine_parity.pio",
    REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_compact_tight_engine_parity.pio",
)
ROW_COUNTED_PIO_SOURCE_CANDIDATES = (
    REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_counted_engine_parity.pio",
    REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_counted_engine_parity.pio",
)
ROW_COUNTED_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_counted_engine.h"
)
ROW_HYBRID_PIO_SOURCE_CANDIDATES = (
    REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_hybrid_engine_parity.pio",
    REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_hybrid_engine_parity.pio",
)
ROW_HYBRID_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_hybrid_engine.h"
)
ROW_RUNS_PIO_SOURCE_CANDIDATES = (
    REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_runs_engine_parity.pio",
    REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_runs_engine_parity.pio",
)
ROW_RUNS_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_runs_engine.h"
)
ROW_SPLIT_PIO_SOURCE_CANDIDATES = (
    REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_split_engine_parity.pio",
    REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_split_engine_parity.pio",
)
ROW_SPLIT_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_split_engine.h"
)
ROW_WINDOW_PIO_SOURCE_CANDIDATES = (
    REPO_ROOT / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_row_window_engine_parity.pio",
    REPO_ROOT / "rust" / "heart_rust" / "pio" / "piomatter_row_window_engine_parity.pio",
)
ROW_WINDOW_RENDER_OVERRIDE = (
    REPO_ROOT / "docs" / "research" / "generated" / "piomatter_override" / "render_row_window_engine.h"
)
RP1_PIO_PARAM_ROOT = DEFAULT_RP1_PIO_PARAM_ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark stock Piomatter versus compact row-engine experiments on static test patterns."
    )
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument(
        "--baseline-variant",
        type=str,
        default=DEFAULT_BASELINE_VARIANT,
        choices=BASELINE_VARIANT_CHOICES,
        help="Variant to run before and after a single experimental variant.",
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--max-xfer-bytes", type=int, default=DEFAULT_MAX_XFER_BYTES)
    parser.add_argument("--n-addr-lines", type=int, default=DEFAULT_N_ADDR_LINES)
    parser.add_argument("--n-planes", type=int, default=DEFAULT_N_PLANES)
    parser.add_argument(
        "--n-temporal-planes",
        type=int,
        default=DEFAULT_N_TEMPORAL_PLANES,
    )
    parser.add_argument("--post-addr-delay", type=int, default=DEFAULT_POST_ADDR_DELAY)
    parser.add_argument("--post-latch-delay", type=int, default=DEFAULT_POST_LATCH_DELAY)
    parser.add_argument("--post-oe-delay", type=int, default=DEFAULT_POST_OE_DELAY)
    parser.add_argument(
        "--rescale-mode",
        type=str,
        default=DEFAULT_RESCALE_MODE,
        choices=RESCALE_MODE_CHOICES,
    )
    parser.add_argument("--pinout", type=str, default=DEFAULT_PINOUT, choices=PINOUT_CHOICES)
    parser.add_argument("--pattern", type=str, default=DEFAULT_PATTERN, choices=PATTERN_CHOICES)
    parser.add_argument("--duration-seconds", type=float, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--warmup-seconds", type=float, default=DEFAULT_WARMUP_SECONDS)
    parser.add_argument("--target-freq-hz", type=int, default=DEFAULT_TARGET_FREQ_HZ)
    parser.add_argument("--variant", type=str, default=DEFAULT_VARIANT, choices=VARIANT_CHOICES)
    parser.add_argument(
        "--baseline-group",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_ENABLE_BASELINE_GROUP,
        help="When benchmarking one non-stock variant, run baseline pre/post measurements too.",
    )
    parser.add_argument(
        "--slab-copies",
        type=str,
        default=DEFAULT_SLAB_COPIES,
        help="Comma-separated slab copy counts for non-stock variants.",
    )
    parser.add_argument(
        "--break-system-packages",
        action="store_true",
        help="Pass Debian's PEP 668 override when reinstalling Piomatter.",
    )
    parser.add_argument(
        "--baseline-rp1-pio-param",
        action="append",
        default=list(DEFAULT_BASELINE_RP1_PIO_PARAMS),
        help="RP1 PIO module parameter override for baseline runs, in NAME=VALUE form. Defaults to tx_mmio_blind=Y.",
    )
    parser.add_argument(
        "--experiment-rp1-pio-param",
        action="append",
        default=list(DEFAULT_EXPERIMENT_RP1_PIO_PARAMS),
        help="RP1 PIO module parameter override for experiment runs, in NAME=VALUE form. Defaults to tx_mmio_blind=Y.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolved_variant = resolve_effective_variant(args.variant, args.pattern)
    resolved_baseline_variant = resolve_effective_variant(args.baseline_variant, args.pattern)
    if uses_row_split_variant(resolved_variant, resolved_baseline_variant) and args.pattern not in {
        "solid-red",
        "quadrants",
    }:
        raise ValueError("row-split only supports solid-red and quadrants patterns")
    if uses_row_window_variant(resolved_variant, resolved_baseline_variant) and args.pattern not in {
        "solid-red",
        "quadrants",
        "center-box",
    }:
        raise ValueError("row-window only supports solid-red, quadrants, and center-box patterns")
    slab_copies = parse_slab_copies(args.slab_copies)
    baseline_param_overrides = parse_rp1_pio_param_overrides(args.baseline_rp1_pio_param)
    experiment_param_overrides = parse_rp1_pio_param_overrides(args.experiment_rp1_pio_param)
    if resolved_variant == "both":
        planned_runs = [PlannedRun("stock", 1), PlannedRun("row-repeat", slab_copies[0])]
    elif resolved_variant == "all":
        planned_runs = [
            PlannedRun("stock", 1),
            PlannedRun("row-repeat", slab_copies[0]),
            PlannedRun("row-compact", slab_copies[0]),
            PlannedRun("row-compact-tight", slab_copies[0]),
            PlannedRun("row-counted", slab_copies[0]),
            PlannedRun("row-hybrid", slab_copies[0]),
            PlannedRun("row-runs", slab_copies[0]),
            PlannedRun("row-window", slab_copies[0]),
        ]
    elif resolved_variant == "stock":
        planned_runs = [PlannedRun("stock", 1)]
    elif args.baseline_group:
        planned_runs = [
            PlannedRun(resolved_baseline_variant, slab_copies[0], group_role="baseline-pre"),
            PlannedRun(resolved_variant, slab_copies[0], group_role="experiment"),
            PlannedRun(resolved_baseline_variant, slab_copies[0], group_role="baseline-post"),
        ]
    else:
        planned_runs = [PlannedRun(resolved_variant, slab_copies[0])]
    results: list[dict[str, float | str | int]] = []
    for planned_run in planned_runs:
        install_variant(
            variant=planned_run.variant,
            checkout=args.checkout,
            break_system_packages=args.break_system_packages,
            slab_copies=planned_run.slab_copies,
            target_freq_hz=args.target_freq_hz,
            max_xfer_bytes=args.max_xfer_bytes,
            post_addr_delay=args.post_addr_delay,
            post_latch_delay=args.post_latch_delay,
            post_oe_delay=args.post_oe_delay,
            rescale_mode=args.rescale_mode,
        )
        with temporary_rp1_pio_param_overrides(
            planned_run.rp1_pio_param_overrides(
                baseline_param_overrides=baseline_param_overrides,
                experiment_param_overrides=experiment_param_overrides,
            )
        ):
            result = benchmark_variant(
                variant=planned_run.display_name(),
                width=args.width,
                height=args.height,
                n_addr_lines=args.n_addr_lines,
                n_planes=args.n_planes,
                n_temporal_planes=args.n_temporal_planes,
                pinout=args.pinout,
                pattern=args.pattern,
                duration_seconds=args.duration_seconds,
                warmup_seconds=args.warmup_seconds,
                target_freq_hz=args.target_freq_hz,
            )
        result["slab_copies"] = planned_run.slab_copies
        result["effective_display_refresh_hz"] = (
            float(result["trimmed_refresh_fps"])
            * planned_run.slab_copies
            / int(result["schedule_groups"])
        )
        result["target_freq_hz"] = args.target_freq_hz
        result["max_xfer_bytes"] = args.max_xfer_bytes
        result["post_addr_delay"] = args.post_addr_delay
        result["post_latch_delay"] = args.post_latch_delay
        result["post_oe_delay"] = args.post_oe_delay
        result["rescale_mode"] = args.rescale_mode
        result["pattern"] = args.pattern
        if planned_run.group_role is not None:
            result["group_role"] = planned_run.group_role
        if args.variant == BEST_KNOWN_VARIANT:
            result["best_known_variant"] = resolved_variant
        if args.baseline_variant == BEST_KNOWN_VARIANT:
            result["best_known_baseline_variant"] = resolved_baseline_variant
        result["rp1_pio_params"] = planned_run.rp1_pio_param_overrides(
            baseline_param_overrides=baseline_param_overrides,
            experiment_param_overrides=experiment_param_overrides,
        )
        results.append(result)

    kernel_releases = {str(result["kernel_release"]) for result in results}
    if len(kernel_releases) > 1:
        LOGGER.warning("Kernel release changed during benchmark group: %s", sorted(kernel_releases))
    baseline_consistent, baseline_drift = grouped_baseline_consistency(results)
    if baseline_drift is not None:
        LOGGER.info("Grouped baseline drift=%.2f%%", baseline_drift * 100.0)

    for result in results:
        LOGGER.info(
            "%s refresh_fps median=%.2f trimmed=%.2f effective_display=%.2f raw_avg=%.2f min=%.2f max=%.2f samples=%s plausible=%s tx_mmio_blind=%s",
            result["variant"],
            result["median_refresh_fps"],
            result["trimmed_refresh_fps"],
            result["effective_display_refresh_hz"],
            result["avg_refresh_fps"],
            result["min_refresh_fps"],
            result["max_refresh_fps"],
            result["sample_count"],
            result["measurement_plausible"],
            result.get("tx_mmio_blind"),
        )
    print(json.dumps(results, indent=2))
    if any(not bool(result["measurement_plausible"]) for result in results):
        LOGGER.error(
            "At least one benchmark result exceeded the shift-only plausibility bound; treat that run as a broken scan path, not a speedup."
        )
        return 1
    if not baseline_consistent:
        LOGGER.error(
            "Grouped baseline drift exceeded the tolerance of %.1f%%; treat that run as unstable.",
            DEFAULT_BASELINE_DRIFT_TOLERANCE * 100.0,
        )
        return 1
    return 0


def install_variant(
    variant: str,
    checkout: Path,
    break_system_packages: bool,
    slab_copies: int,
    target_freq_hz: int,
    max_xfer_bytes: int,
    post_addr_delay: int,
    post_latch_delay: int,
    post_oe_delay: int,
    rescale_mode: str,
) -> None:
    if variant == "stock":
        command = [sys.executable, "-m", "pip", "install", "--user", "--force-reinstall"]
        if break_system_packages:
            command.append("--break-system-packages")
        command.append("Adafruit-Blinka-Raspberry-Pi5-Piomatter")
        run_command(command)
        return

    pio_source, render_override = variant_assets(variant)
    run_command(
        [
            sys.executable,
            str(PREPARE_SCRIPT),
            "--checkout",
            str(checkout),
            "--pio-source",
            str(pio_source),
            "--render-override",
            str(render_override),
            "--slab-copies",
            str(slab_copies),
            "--target-freq-hz",
            str(target_freq_hz),
            "--max-xfer-bytes",
            str(max_xfer_bytes),
            "--post-addr-delay",
            str(post_addr_delay),
            "--post-latch-delay",
            str(post_latch_delay),
            "--post-oe-delay",
            str(post_oe_delay),
            "--rescale-mode",
            rescale_mode,
        ]
    )
    install_command = [sys.executable, "-m", "pip", "install", "--user", "--force-reinstall"]
    if break_system_packages:
        install_command.append("--break-system-packages")
    clean_checkout_build_artifacts(checkout)
    install_command.append(str(checkout))
    run_command(
        install_command,
        extra_env={
            "CFLAGS": DEFAULT_BUILD_CFLAGS,
            "CXXFLAGS": DEFAULT_BUILD_CXXFLAGS,
        },
    )
    time.sleep(DEFAULT_INSTALL_SETTLE_SECONDS)


def resolve_row_repeat_pio_source() -> Path:
    for candidate in ROW_REPEAT_PIO_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return ROW_REPEAT_PIO_SOURCE_CANDIDATES[0]


def resolve_row_compact_pio_source() -> Path:
    for candidate in ROW_COMPACT_PIO_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return ROW_COMPACT_PIO_SOURCE_CANDIDATES[0]


def resolve_row_compact_tight_pio_source() -> Path:
    for candidate in ROW_COMPACT_TIGHT_PIO_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return ROW_COMPACT_TIGHT_PIO_SOURCE_CANDIDATES[0]


def resolve_row_counted_pio_source() -> Path:
    for candidate in ROW_COUNTED_PIO_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return ROW_COUNTED_PIO_SOURCE_CANDIDATES[0]


def resolve_row_hybrid_pio_source() -> Path:
    for candidate in ROW_HYBRID_PIO_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return ROW_HYBRID_PIO_SOURCE_CANDIDATES[0]


def resolve_row_runs_pio_source() -> Path:
    for candidate in ROW_RUNS_PIO_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return ROW_RUNS_PIO_SOURCE_CANDIDATES[0]


def resolve_row_split_pio_source() -> Path:
    for candidate in ROW_SPLIT_PIO_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return ROW_SPLIT_PIO_SOURCE_CANDIDATES[0]


def resolve_row_window_pio_source() -> Path:
    for candidate in ROW_WINDOW_PIO_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return ROW_WINDOW_PIO_SOURCE_CANDIDATES[0]


def variant_assets(variant: str) -> tuple[Path, Path]:
    if variant == "row-repeat":
        return resolve_row_repeat_pio_source(), ROW_REPEAT_RENDER_OVERRIDE
    if variant == "row-compact":
        return resolve_row_compact_pio_source(), ROW_COMPACT_RENDER_OVERRIDE
    if variant == "row-compact-tight":
        return resolve_row_compact_tight_pio_source(), ROW_COMPACT_RENDER_OVERRIDE
    if variant == "row-counted":
        return resolve_row_counted_pio_source(), ROW_COUNTED_RENDER_OVERRIDE
    if variant == "row-hybrid":
        return resolve_row_hybrid_pio_source(), ROW_HYBRID_RENDER_OVERRIDE
    if variant == "row-runs":
        return resolve_row_runs_pio_source(), ROW_RUNS_RENDER_OVERRIDE
    if variant == "row-split":
        return resolve_row_split_pio_source(), ROW_SPLIT_RENDER_OVERRIDE
    if variant == "row-window":
        return resolve_row_window_pio_source(), ROW_WINDOW_RENDER_OVERRIDE
    raise ValueError(f"Unsupported non-stock variant: {variant}")

def uses_row_split_variant(variant: str, baseline_variant: str) -> bool:
    return variant == "row-split" or baseline_variant == "row-split"


def uses_row_window_variant(variant: str, baseline_variant: str) -> bool:
    return variant == "row-window" or baseline_variant == "row-window"


def resolve_effective_variant(variant: str, pattern: str) -> str:
    if variant != BEST_KNOWN_VARIANT:
        return variant
    if pattern == "center-box":
        return "row-window"
    return "row-compact"


class PlannedRun:
    def __init__(self, variant: str, slab_copies: int, group_role: str | None = None) -> None:
        self.variant = variant
        self.slab_copies = slab_copies
        self.group_role = group_role

    def display_name(self) -> str:
        base_name = self.variant if self.variant == "stock" else f"{self.variant}-x{self.slab_copies}"
        if self.group_role is None:
            return base_name
        return f"{base_name}-{self.group_role}"

    def rp1_pio_param_overrides(
        self,
        *,
        baseline_param_overrides: dict[str, str],
        experiment_param_overrides: dict[str, str],
    ) -> dict[str, str]:
        if self.group_role in {"baseline-pre", "baseline-post"}:
            return baseline_param_overrides
        if self.group_role == "experiment":
            return experiment_param_overrides
        return experiment_param_overrides


def parse_slab_copies(raw_value: str) -> tuple[int, ...]:
    values = []
    for raw_part in raw_value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        value = int(part)
        if value < 1:
            raise ValueError("slab copy counts must be at least 1")
        values.append(value)
    if not values:
        raise ValueError("at least one slab copy count is required")
    return tuple(values)


def parse_rp1_pio_param_overrides(raw_values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for raw_value in raw_values:
        if "=" not in raw_value:
            raise ValueError(
                f"RP1 PIO parameter override {raw_value!r} must use NAME=VALUE syntax"
            )
        name, value = raw_value.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or not value:
            raise ValueError(
                f"RP1 PIO parameter override {raw_value!r} must include both name and value"
            )
        overrides[name] = value
    return overrides


def read_rp1_pio_parameter(name: str) -> str:
    parameter_path = RP1_PIO_PARAM_ROOT / name
    if not parameter_path.exists():
        raise FileNotFoundError(f"RP1 PIO parameter {name!r} does not exist at {parameter_path}")
    return parameter_path.read_text(encoding="utf-8").strip()


def write_rp1_pio_parameter(name: str, value: str) -> None:
    parameter_path = RP1_PIO_PARAM_ROOT / name
    if not parameter_path.exists():
        raise FileNotFoundError(f"RP1 PIO parameter {name!r} does not exist at {parameter_path}")
    LOGGER.info("Setting RP1 PIO parameter %s=%s", name, value)
    subprocess.run(
        ["sudo", "/usr/bin/tee", str(parameter_path)],
        input=f"{value}\n",
        text=True,
        stdout=subprocess.DEVNULL,
        check=True,
    )


@contextmanager
def temporary_rp1_pio_param_overrides(overrides: dict[str, str]):
    if not overrides:
        yield
        return

    original_values = {name: read_rp1_pio_parameter(name) for name in overrides}
    try:
        for name, value in overrides.items():
            if original_values[name] != value:
                write_rp1_pio_parameter(name, value)
        yield
    finally:
        for name, value in original_values.items():
            if read_rp1_pio_parameter(name) != value:
                write_rp1_pio_parameter(name, value)


def benchmark_variant(
    *,
    variant: str,
    width: int,
    height: int,
    n_addr_lines: int,
    n_planes: int,
    n_temporal_planes: int,
    pinout: str,
    pattern: str,
    duration_seconds: float,
    warmup_seconds: float,
    target_freq_hz: int,
) -> dict[str, float | str | int]:
    schedule_groups = max(1, n_temporal_planes)
    rows_per_scan = 1 << n_addr_lines
    shift_only_ceiling_hz = target_freq_hz / (2 * width * rows_per_scan * max(1, n_planes))
    benchmark_code = f"""
import gc
import json
import platform
import statistics
import time
from pathlib import Path
import numpy as np
import adafruit_blinka_raspberry_pi5_piomatter as piomatter

def fill_pattern(framebuffer, pattern_name):
    framebuffer[:, :, :] = 0
    if pattern_name == "solid-red":
        framebuffer[:, :, 0] = 255
        return
    if pattern_name == "quadrants":
        half_height = framebuffer.shape[0] // 2
        half_width = framebuffer.shape[1] // 2
        framebuffer[:half_height, :half_width, :] = (255, 0, 0)
        framebuffer[:half_height, half_width:, :] = (0, 255, 0)
        framebuffer[half_height:, :half_width, :] = (0, 0, 255)
        framebuffer[half_height:, half_width:, :] = (255, 255, 255)
        return
    if pattern_name == "center-box":
        box_height = max(4, framebuffer.shape[0] // 4)
        box_width = max(4, framebuffer.shape[1] // 8)
        start_y = (framebuffer.shape[0] - box_height) // 2
        start_x = (framebuffer.shape[1] - box_width) // 2
        framebuffer[start_y : start_y + box_height, start_x : start_x + box_width, :] = (255, 255, 255)
        return
    raise ValueError(f"Unsupported benchmark pattern: {{pattern_name}}")

geometry = piomatter.Geometry(
    width={width},
    height={height},
    n_addr_lines={n_addr_lines},
    rotation=piomatter.Orientation.Normal,
    n_planes={n_planes},
    n_temporal_planes={n_temporal_planes},
)
framebuffer = np.zeros((geometry.height, geometry.width, 3), dtype=np.uint8)
fill_pattern(framebuffer, {pattern!r})
matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,
    pinout=getattr(piomatter.Pinout, {PINOUT_NAMES[pinout]!r}),
    framebuffer=framebuffer,
    geometry=geometry,
)
matrix.show()
time.sleep({warmup_seconds})
samples = []
deadline = time.monotonic() + {duration_seconds}
while time.monotonic() < deadline:
    samples.append(float(matrix.fps))
    time.sleep(0.2)
sorted_samples = sorted(samples)
trim_count = 1 if len(sorted_samples) >= 5 else 0
if len(sorted_samples) > trim_count * 2:
    trimmed_samples = sorted_samples[trim_count: len(sorted_samples) - trim_count]
else:
    trimmed_samples = sorted_samples
raw_avg_refresh_fps = sum(samples) / len(samples)
trimmed_refresh_fps = sum(trimmed_samples) / len(trimmed_samples)
median_refresh_fps = statistics.median(sorted_samples)
param_root = Path("/sys/module/rp1_pio/parameters")

def read_param(name, default="unknown"):
    path = param_root / name
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8").strip()

result = {{
    "variant": {variant!r},
    "n_planes": {n_planes},
    "n_temporal_planes": {n_temporal_planes},
    "schedule_groups": {schedule_groups},
    "schedule_refresh_hz": trimmed_refresh_fps,
    "avg_refresh_fps": raw_avg_refresh_fps,
    "median_refresh_fps": median_refresh_fps,
    "trimmed_refresh_fps": trimmed_refresh_fps,
    "estimated_full_frame_hz": trimmed_refresh_fps / {schedule_groups},
    "macrocycle_hz": trimmed_refresh_fps / {schedule_groups},
    "min_refresh_fps": min(samples),
    "max_refresh_fps": max(samples),
    "sample_count": len(samples),
    "kernel_release": platform.release(),
    "shift_only_ceiling_hz": {shift_only_ceiling_hz},
    "measurement_plausible": trimmed_refresh_fps <= {shift_only_ceiling_hz * DEFAULT_SHIFT_ONLY_PLAUSIBILITY_MARGIN},
    "tx_mmio_blind": read_param("tx_mmio_blind"),
}}
del matrix
gc.collect()
time.sleep({DEFAULT_POST_MATRIX_DESTROY_SECONDS})
print(json.dumps(result))
"""
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(DEFAULT_BENCHMARK_ATTEMPTS):
        completed = subprocess.run(
            [sys.executable, "-c", benchmark_code],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return json.loads(completed.stdout.strip().splitlines()[-1])
        last_error = subprocess.CalledProcessError(
            completed.returncode,
            completed.args,
            output=completed.stdout,
            stderr=completed.stderr,
        )
        LOGGER.warning(
            "Benchmark attempt %s/%s for %s failed with exit %s.\nstdout:\n%s\nstderr:\n%s",
            attempt + 1,
            DEFAULT_BENCHMARK_ATTEMPTS,
            variant,
            completed.returncode,
            completed.stdout.strip(),
            completed.stderr.strip(),
        )
        time.sleep(DEFAULT_BENCHMARK_RETRY_DELAY_SECONDS)
    assert last_error is not None
    raise last_error


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


def grouped_baseline_consistency(
    results: list[dict[str, float | str | int]],
) -> tuple[bool, float | None]:
    grouped_results = {
        str(result.get("group_role")): result for result in results if result.get("group_role") is not None
    }
    baseline_pre = grouped_results.get("baseline-pre")
    baseline_post = grouped_results.get("baseline-post")
    if baseline_pre is None or baseline_post is None:
        return True, None
    pre_refresh = float(baseline_pre["trimmed_refresh_fps"])
    post_refresh = float(baseline_post["trimmed_refresh_fps"])
    baseline_max = max(pre_refresh, post_refresh)
    if baseline_max <= 0:
        return False, 1.0
    drift = abs(pre_refresh - post_refresh) / baseline_max
    return drift <= DEFAULT_BASELINE_DRIFT_TOLERANCE, drift


def run_command(command: list[str], extra_env: dict[str, str] | None = None) -> None:
    LOGGER.info("Running %s", command)
    env = None
    if extra_env is not None:
        env = {**os.environ, **extra_env}
    subprocess.run(command, check=True, cwd=REPO_ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
