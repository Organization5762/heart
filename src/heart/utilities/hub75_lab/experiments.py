"""The retained, parameterized HUB75 experiment catalog."""

from __future__ import annotations

import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import final

from heart.utilities.hub75_lab._bundle import normalize_host
from heart.utilities.hub75_lab._execution import ExperimentCommand

KNOWN_GOOD_CANDIDATE = (
    "state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2"
)
KNOWN_GOOD_FRAME_SLOT_OFFSET = 0xB800
KNOWN_GOOD_PWM_BITS = 6
CANDIDATE_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
DEFAULT_ROWS = 64
DEFAULT_COLS = 64
DEFAULT_CHAIN_LENGTH = 1
DEFAULT_PARALLEL = 1
DEFAULT_HARDWARE_MAPPING = "adafruit-hat-pwm"
DEFAULT_LED_RGB_SEQUENCE = "RGB"
APPLIED_SETTING_NAMES = {
    "runtime-color-cycle": (
        "rows",
        "cols",
        "chain_length",
        "parallel",
        "hardware_mapping",
        "led_rgb_sequence",
        "seconds",
        "intensities",
    ),
    "runtime-gradient": (
        "rows",
        "cols",
        "chain_length",
        "parallel",
        "hardware_mapping",
        "led_rgb_sequence",
        "seconds",
    ),
    "runtime-single-line": (
        "rows",
        "cols",
        "chain_length",
        "parallel",
        "hardware_mapping",
        "led_rgb_sequence",
        "seconds",
        "row_index",
        "line_thickness",
        "red",
        "green",
        "blue",
    ),
    "gpio-smoke": (
        "rows",
        "cols",
        "seconds",
        "row_index",
        "red",
        "green",
        "blue",
        "row_dwell_seconds",
        "gpio_diagnostic_mode",
    ),
    "totem3-known-good-blue": (
        "target",
        "seconds",
        "strict_hashes",
    ),
    "regular-p0p1-direct": (
        "target",
        "seconds",
        "pwm_bits",
        "candidate",
        "frame_slot_offset",
    ),
}
EXPERIMENT_SPECS = (
    (
        "runtime-color-cycle",
        "Clean-room runtime RGB primary/intensity wiring check.",
        "heart.utilities.hub75_lab._backends",
        True,
    ),
    (
        "runtime-gradient",
        "Clean-room runtime full-frame color/order continuity check.",
        "heart.utilities.hub75_lab._backends",
        True,
    ),
    (
        "runtime-single-line",
        "Clean-room runtime row-address and blanking isolation check.",
        "heart.utilities.hub75_lab._backends",
        True,
    ),
    (
        "gpio-smoke",
        "Slow direct-GPIO wiring check that bypasses the scan transport.",
        "heart.utilities.hub75_lab._backends",
        True,
    ),
    (
        "totem3-known-good-blue",
        "Self-contained known-good 500 Hz state32 blue reproduction.",
        "scripts/rp1_hub75_reproduce_totem_blue.sh",
        True,
    ),
    (
        "regular-p0p1-direct",
        "Audited regular P0/P1 chain2 direct state32 packer bypass.",
        "scripts/rp1_hub75_run_direct_state32_regular.sh",
        True,
    ),
)


def list_experiments() -> tuple[Experiment, ...]:
    """Return the stable retained experiment catalog."""

    return tuple(Experiment(*spec) for spec in EXPERIMENT_SPECS)


def build_experiment_command(
    *,
    repo_root: Path,
    name: str,
    settings: ExperimentSettings,
) -> ExperimentCommand:
    """Resolve one retained experiment into an explicit command and environment."""

    settings.validate()
    experiment = _experiment_by_name(name)
    _reject_ignored_settings(name, settings)
    implementation = repo_root / experiment.implementation

    common_runtime_args = (
        "--rows",
        str(settings.rows),
        "--cols",
        str(settings.cols),
        "--chain-length",
        str(settings.chain_length),
        "--parallel",
        str(settings.parallel),
        "--hardware-mapping",
        settings.hardware_mapping,
        "--led-rgb-sequence",
        settings.led_rgb_sequence,
    )
    environment: dict[str, str] = {}
    argv: tuple[str, ...]
    safety_evidence: tuple[str, ...] = (
        "No temporal-PWM parameter is exposed by the retained runner.",
    )

    if name == "runtime-color-cycle":
        argv = (
            sys.executable,
            "-m",
            experiment.implementation,
            name,
            *common_runtime_args,
            "--seconds",
            str(settings.seconds),
            "--intensities",
            settings.intensities,
        )
    elif name == "runtime-gradient":
        argv = (
            sys.executable,
            "-m",
            experiment.implementation,
            name,
            *common_runtime_args,
            "--seconds",
            str(settings.seconds),
        )
    elif name == "runtime-single-line":
        argv = (
            sys.executable,
            "-m",
            experiment.implementation,
            name,
            *common_runtime_args,
            "--seconds",
            str(settings.seconds),
            "--row-index",
            str(settings.row_index),
            "--line-thickness",
            str(settings.line_thickness),
            "--red",
            str(settings.red),
            "--green",
            str(settings.green),
            "--blue",
            str(settings.blue),
        )
    elif name == "gpio-smoke":
        argv = (
            sys.executable,
            "-m",
            experiment.implementation,
            name,
            "--rows",
            str(settings.rows),
            "--cols",
            str(settings.cols),
            "--seconds",
            str(settings.seconds),
            "--row-dwell-seconds",
            str(settings.row_dwell_seconds),
            "--gpio-diagnostic-mode",
            settings.gpio_diagnostic_mode,
            "--row-index",
            str(settings.row_index),
            "--red",
            str(settings.red),
            "--green",
            str(settings.green),
            "--blue",
            str(settings.blue),
        )
    elif name == "totem3-known-good-blue":
        if not implementation.is_file():
            raise ValueError(f"missing retained implementation: {implementation}")
        target = normalize_host(settings.target)
        if settings.candidate != KNOWN_GOOD_CANDIDATE:
            raise ValueError(
                "totem3-known-good-blue fixes the proven scanner candidate; "
                "use regular-p0p1-direct for candidate experiments"
            )
        if settings.pwm_bits != KNOWN_GOOD_PWM_BITS:
            raise ValueError(
                f"totem3-known-good-blue requires pwm_bits={KNOWN_GOOD_PWM_BITS}"
            )
        if settings.frame_slot_offset != KNOWN_GOOD_FRAME_SLOT_OFFSET:
            raise ValueError(
                "totem3-known-good-blue requires frame_slot_offset=0xb800"
            )
        argv = (str(implementation), target)
        environment = {
            "RP1_HUB75_SECONDS": str(settings.seconds),
            "RP1_HUB75_STRICT_HASHES": "1" if settings.strict_hashes else "0",
        }
        safety_evidence += (
            "Delegates to the self-contained Heart Linux bundle reproduction; "
            "the Rust color-loop runner is not used.",
            "Publishes the 0xb800 slot before the scanner starts.",
            (
                "Payload and module hashes are enforced."
                if settings.strict_hashes
                else (
                    "The payload hash is enforced; module srcversion and SHA-256 "
                    "are reported but not enforced."
                )
            ),
        )
    elif name == "regular-p0p1-direct":
        if not implementation.is_file():
            raise ValueError(f"missing retained implementation: {implementation}")
        target = normalize_host(settings.target)
        if settings.frame_slot_offset != KNOWN_GOOD_FRAME_SLOT_OFFSET:
            raise ValueError(
                "regular-p0p1-direct currently requires frame_slot_offset=0xb800"
            )
        argv = (str(implementation), target)
        environment = {
            "RP1_HUB75_SECONDS": str(settings.seconds),
            "RP1_HUB75_PWM_BITS": str(settings.pwm_bits),
            "RP1_HUB75_FRAME_SLOT_OFFSET": hex(settings.frame_slot_offset),
            "RP1_HUB75_SCANNER_CANDIDATE": settings.candidate,
        }
        safety_evidence += (
            "The retained direct script installs its publisher in "
            "RP1_HUB75_PRE_START_COMMAND, freshly republishing 0xb800 after "
            "payload load and before START_MAGIC.",
        )
    else:  # pragma: no cover - guarded by catalog lookup
        raise AssertionError(name)

    return ExperimentCommand(
        argv=argv,
        environment=environment,
        cwd=repo_root,
        safety_evidence=safety_evidence,
        applied_settings=_applied_settings(name, settings),
        fixed_invariants=_fixed_invariants(name),
    )


@final
@dataclass(frozen=True)
class Experiment:
    """One trusted experiment exposed by the calm runner."""

    name: str
    summary: str
    implementation: str
    mutates_hardware: bool


@final
@dataclass(frozen=True)
class ExperimentSettings:
    """Explicit parameters shared by retained HUB75 experiments."""

    target: str = "michael@totem3.local"
    rows: int = DEFAULT_ROWS
    cols: int = DEFAULT_COLS
    chain_length: int = DEFAULT_CHAIN_LENGTH
    parallel: int = DEFAULT_PARALLEL
    hardware_mapping: str = DEFAULT_HARDWARE_MAPPING
    led_rgb_sequence: str = DEFAULT_LED_RGB_SEQUENCE
    seconds: float = 5.0
    pwm_bits: int = KNOWN_GOOD_PWM_BITS
    candidate: str = KNOWN_GOOD_CANDIDATE
    frame_slot_offset: int = KNOWN_GOOD_FRAME_SLOT_OFFSET
    strict_hashes: bool = False
    intensities: str = "32,96,160,255"
    row_index: int = 0
    line_thickness: int = 1
    red: int = 255
    green: int = 255
    blue: int = 255
    row_dwell_seconds: float = 0.0005
    gpio_diagnostic_mode: str = "scan"

    def validate(self) -> None:
        """Reject invalid settings before planning or hardware mutation."""

        if self.rows <= 0 or self.rows % 2:
            raise ValueError(f"rows must be a positive even number, got {self.rows}")
        if self.cols <= 0:
            raise ValueError(f"cols must be positive, got {self.cols}")
        if self.chain_length <= 0:
            raise ValueError(
                f"chain_length must be positive, got {self.chain_length}"
            )
        if self.parallel <= 0:
            raise ValueError(f"parallel must be positive, got {self.parallel}")
        if self.seconds <= 0:
            raise ValueError(f"seconds must be positive, got {self.seconds}")
        if self.pwm_bits < 1 or self.pwm_bits > 11:
            raise ValueError(f"pwm_bits must be in [1, 11], got {self.pwm_bits}")
        if self.frame_slot_offset < 0:
            raise ValueError(
                f"frame_slot_offset must be non-negative, got {self.frame_slot_offset}"
            )
        if CANDIDATE_TOKEN_PATTERN.fullmatch(self.candidate) is None:
            raise ValueError(
                "candidate must contain only launcher token characters "
                "[A-Za-z0-9._-]"
            )
        if self.hardware_mapping not in ("adafruit-hat", "adafruit-hat-pwm"):
            raise ValueError(
                f"unsupported hardware_mapping {self.hardware_mapping!r}"
            )
        if self.led_rgb_sequence.upper() not in {
            "RGB",
            "RBG",
            "GRB",
            "GBR",
            "BRG",
            "BGR",
        }:
            raise ValueError(
                f"unsupported led_rgb_sequence {self.led_rgb_sequence!r}"
            )
        intensity_values = tuple(
            component.strip()
            for component in self.intensities.split(",")
            if component.strip()
        )
        if not intensity_values:
            raise ValueError("intensities must contain at least one value")
        try:
            parsed_intensities = tuple(int(value) for value in intensity_values)
        except ValueError as error:
            raise ValueError("intensities must be comma-separated integers") from error
        if any(value < 0 or value > 255 for value in parsed_intensities):
            raise ValueError("intensities must be in [0, 255]")
        if self.gpio_diagnostic_mode not in {
            "scan",
            "hold-row",
            "latch-pulse",
            "walking-bit",
        }:
            raise ValueError(
                f"unsupported gpio_diagnostic_mode {self.gpio_diagnostic_mode!r}"
            )
        if self.row_index < 0 or self.row_index >= self.rows:
            raise ValueError(
                f"row_index must be in [0, {self.rows - 1}], got {self.row_index}"
            )
        if self.line_thickness <= 0 or self.row_index + self.line_thickness > self.rows:
            raise ValueError(
                "line_thickness must keep the line inside the configured rows"
            )
        for name, value in (
            ("red", self.red),
            ("green", self.green),
            ("blue", self.blue),
        ):
            if value < 0 or value > 255:
                raise ValueError(f"{name} must be in [0, 255], got {value}")
        if self.row_dwell_seconds <= 0:
            raise ValueError(
                "row_dwell_seconds must be positive, "
                f"got {self.row_dwell_seconds}"
            )


def _experiment_by_name(name: str) -> Experiment:
    experiments = list_experiments()
    for experiment in experiments:
        if experiment.name == name:
            return experiment
    choices = ", ".join(experiment.name for experiment in experiments)
    raise ValueError(f"unknown experiment {name!r}; choose one of: {choices}")


def _reject_ignored_settings(name: str, settings: ExperimentSettings) -> None:
    allowed = set(APPLIED_SETTING_NAMES[name])
    defaults = asdict(ExperimentSettings())
    observed = asdict(settings)
    ignored_nondefault = {
        field: value
        for field, value in observed.items()
        if field not in allowed and value != defaults[field]
    }
    if ignored_nondefault:
        details = ", ".join(
            f"{field}={value!r}" for field, value in ignored_nondefault.items()
        )
        raise ValueError(
            f"experiment {name!r} does not accept these settings: {details}"
        )


def _applied_settings(
    name: str,
    settings: ExperimentSettings,
) -> dict[str, object]:
    observed = asdict(settings)
    return {field: observed[field] for field in APPLIED_SETTING_NAMES[name]}


def _fixed_invariants(name: str) -> dict[str, object]:
    invariants: dict[str, object] = {"temporal_pwm": "forbidden"}
    if name == "totem3-known-good-blue":
        invariants.update(
            {
                "transport_geometry": "256x64 A B C D",
                "candidate": KNOWN_GOOD_CANDIDATE,
                "pwm_bits": KNOWN_GOOD_PWM_BITS,
                "frame_slot_offset": "0xb800",
                "implementation": "self-contained Heart Linux bundle",
                "rust_color_loop": "not used",
            }
        )
    elif name == "regular-p0p1-direct":
        invariants.update(
            {
                "transport_geometry": "256x64 regular P0/P1 chain2",
                "fresh_publish_phase": "RP1_HUB75_PRE_START_COMMAND before START_MAGIC",
            }
        )
    elif name == "gpio-smoke":
        invariants["oe_waveform"] = "GPIO18 and legacy GPIO4 mirrored active-low"
    return invariants
