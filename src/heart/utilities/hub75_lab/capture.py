"""Logic2 preflight and complete HUB75 capture evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import shlex
import subprocess
from bisect import bisect_left, bisect_right
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, cast, final

from PIL import Image

from heart.utilities.hub75_logic_score import (Hub75CaptureDiagnosis,
                                               Hub75SimilarityScore,
                                               LogicChannelActivity,
                                               diagnose_hub75_capture,
                                               load_hub75_logic_csv,
                                               summarize_logic_channels)

COLOR_SIGNALS = ("R1", "G1", "B1", "R2", "G2", "B2")
CONTROL_SIGNALS = ("CLK", "LAT", "OE")
ADDRESS_SIGNALS = ("A", "B", "C", "D", "E")
REQUIRED_CAPTURE_SIGNALS = CONTROL_SIGNALS + ADDRESS_SIGNALS[:4] + COLOR_SIGNALS
DEFAULT_CAPTURE_SIGNAL_MAP = {
    "R1": 0,
    "B1": 1,
    "R2": 2,
    "B2": 3,
    "A": 4,
    "C": 5,
    "CLK": 6,
    "OE": 7,
    "G1": 8,
    "LAT": 9,
    "D": 10,
    "B": 11,
    "G2": 13,
}
COMPLETE_SIMILARITY_CONTROL_WEIGHT = 0.75
COMPLETE_SIMILARITY_COLOR_WEIGHT = 0.25
COMPLETE_SIMILARITY_PASS_THRESHOLD = 0.90


def analyze_capture(
    path: str | Path,
    *,
    preflight: CapturePreflight,
    signal_map: Mapping[str, int],
    cols: int,
    expected_active_colors: tuple[str, ...],
    require_trusted: bool = True,
) -> CaptureReport:
    """Validate capture provenance and summarize control plus color activity."""

    return _analyze_capture_with_saleae_module(
        path,
        preflight=preflight,
        signal_map=signal_map,
        cols=cols,
        expected_active_colors=expected_active_colors,
        require_trusted=require_trusted,
        saleae_module_name="saleae",
    )


def _analyze_capture_with_saleae_module(
    path: str | Path,
    *,
    preflight: CapturePreflight,
    signal_map: Mapping[str, int],
    cols: int,
    expected_active_colors: tuple[str, ...],
    require_trusted: bool,
    saleae_module_name: str,
) -> CaptureReport:
    """Internal test seam for module discovery; public trust requires Saleae."""

    provenance = preflight._validate_saleae_module(saleae_module_name)
    return _analyze_capture_file(
        path,
        signal_map=signal_map,
        cols=cols,
        expected_active_colors=expected_active_colors,
        target_host=preflight.target_host,
        probe_host=preflight.probe_host,
        provenance=provenance,
        require_trusted=require_trusted,
    )


def _analyze_capture_data(
    path: str | Path,
    *,
    signal_map: Mapping[str, int],
    cols: int,
    expected_active_colors: tuple[str, ...],
    target_host: str,
    probe_host: str,
) -> CaptureReport:
    """Return diagnostic electrical evidence that carries no trusted provenance."""

    return _analyze_capture_file(
        path,
        signal_map=signal_map,
        cols=cols,
        expected_active_colors=expected_active_colors,
        target_host=target_host,
        probe_host=probe_host,
        provenance=None,
        require_trusted=False,
    )


def _analyze_capture_file(
    path: str | Path,
    *,
    signal_map: Mapping[str, int],
    cols: int,
    expected_active_colors: tuple[str, ...],
    target_host: str,
    probe_host: str,
    provenance: _CaptureProvenance | None,
    require_trusted: bool,
) -> CaptureReport:
    """Summarize one exported capture with explicit provenance state."""

    capture_path = Path(path)
    if not capture_path.is_file():
        raise ValueError(f"capture CSV does not exist: {capture_path}")

    normalized_map = {name.upper(): channel for name, channel in signal_map.items()}
    diagnosis = diagnose_hub75_capture(
        capture_path,
        signal_map=normalized_map,
        cols=cols,
    )
    capture = load_hub75_logic_csv(capture_path, normalized_map)
    normalized_expected_colors = tuple(
        signal.upper() for signal in expected_active_colors
    )
    unknown_expected_colors = sorted(
        set(normalized_expected_colors) - set(COLOR_SIGNALS)
    )
    if unknown_expected_colors:
        raise ValueError(
            f"unknown expected color signals: {', '.join(unknown_expected_colors)}"
        )
    color_evidence = {
        signal: _signal_evidence(capture, signal) for signal in COLOR_SIGNALS
    }
    color_edge_counts = {
        signal: evidence.edge_count if evidence is not None else None
        for signal, evidence in color_evidence.items()
    }
    control_edge_counts = {
        signal: len(capture.edges[capture.signal_map[signal]])
        for signal in CONTROL_SIGNALS
    }
    address_edge_counts = {
        signal: (
            len(capture.edges[capture.signal_map[signal]])
            if signal in capture.signal_map
            else None
        )
        for signal in ADDRESS_SIGNALS
    }
    missing_color_signals = tuple(
        signal for signal, count in color_edge_counts.items() if count is None
    )
    missing_required_signals = tuple(
        signal for signal in REQUIRED_CAPTURE_SIGNALS if signal not in capture.signal_map
    )

    report = CaptureReport(
        path=capture_path,
        capture_sha256=_sha256(capture_path),
        target_host=target_host,
        probe_host=probe_host,
        diagnosis=diagnosis,
        control_edge_counts=control_edge_counts,
        address_edge_counts=address_edge_counts,
        color_edge_counts=color_edge_counts,
        color_evidence=color_evidence,
        missing_color_signals=missing_color_signals,
        missing_required_signals=missing_required_signals,
        expected_active_colors=normalized_expected_colors,
        provenance=provenance,
    )
    if require_trusted:
        report.require_trusted()
    return report


def capture_report_payload(report: CaptureReport) -> dict[str, Any]:
    """Return JSON-ready capture evidence with active-low OE duty called out."""

    summary = report.diagnosis.summary
    return {
        "path": str(report.path),
        "capture_sha256": report.capture_sha256,
        "target_host": report.target_host,
        "probe_host": report.probe_host,
        "diagnosis": report.diagnosis.diagnosis,
        "valid_hub75": summary.valid_hub75,
        "oe_active_low_duty": {
            "active_fraction": summary.oe_active_fraction,
            "blank_fraction": summary.oe_blank_fraction,
            "median_active_ns": summary.median_oe_active_ns,
            "median_blank_ns": summary.median_oe_blank_ns,
            "p99_active_ns": summary.p99_oe_active_ns,
            "p99_blank_ns": summary.p99_oe_blank_ns,
            "max_active_ns": summary.max_oe_active_ns,
            "max_blank_ns": summary.max_oe_blank_ns,
        },
        "clock": {
            "edge_count": report.control_edge_counts["CLK"],
            "median_period_ns": summary.median_clk_period_ns,
            "median_high_ns": summary.median_clk_high_ns,
            "median_low_ns": summary.median_clk_low_ns,
            "p99_period_ns": summary.p99_clk_period_ns,
            "p99_high_ns": summary.p99_clk_high_ns,
            "p99_low_ns": summary.p99_clk_low_ns,
            "max_period_ns": summary.max_clk_period_ns,
            "max_high_ns": summary.max_clk_high_ns,
            "max_low_ns": summary.max_clk_low_ns,
            "median_clocks_per_row": summary.median_clocks_per_row,
        },
        "latch": {
            "edge_count": report.control_edge_counts["LAT"],
            "rise_count": summary.lat_rise_count,
            "while_output_enabled_count": summary.lat_while_output_enabled_count,
        },
        "address_edge_counts": report.address_edge_counts,
        "address_max_edge_interval_ns": summary.max_address_edge_interval_ns,
        "color_edge_counts": report.color_edge_counts,
        "color_signal_evidence": {
            signal: asdict(evidence) if evidence is not None else None
            for signal, evidence in report.color_evidence.items()
        },
        "expected_active_colors": list(report.expected_active_colors),
        "color_pattern_valid": report.color_pattern_valid,
        "color_evidence_complete": not report.missing_color_signals,
        "missing_color_signals": list(report.missing_color_signals),
        "trusted_comparison_evidence": report.is_trusted,
        "provenance": (
            asdict(report.provenance) if report.provenance is not None else None
        ),
        "validity_issues": list(summary.validity_issues),
        "warnings": list(summary.warnings),
        "active_channels": [
            asdict(activity) for activity in report.diagnosis.active_channels
        ],
    }


def create_probe_proof(
    capture_path: str | Path,
    *,
    target_host: str,
    probe_host: str,
    proof_signal: str,
    signal_map: Mapping[str, int],
    execution_artifact: str | Path,
    output_path: str | Path,
) -> Path:
    """Correlate a runner-produced host toggle with its named capture channel."""

    normalized_target = _normalize_host_identity(target_host)
    normalized_probe = _normalize_host_identity(probe_host)
    if normalized_target != normalized_probe:
        raise ValueError(
            f"probe host {probe_host!r} does not match target host {target_host!r}"
        )
    normalized_signal = proof_signal.upper()
    if normalized_signal != "CLK":
        raise ValueError(
            "host proof currently requires CLK; OE and color signals are not safe "
            "for slow identification toggles"
        )
    normalized_map = {name.upper(): channel for name, channel in signal_map.items()}
    if normalized_signal not in normalized_map:
        raise ValueError(f"proof signal {normalized_signal!r} is not mapped")
    execution_path = Path(execution_artifact)
    execution = _load_probe_execution(execution_path)
    if _normalize_host_identity(str(execution["target_host"])) != normalized_target:
        raise ValueError("probe execution target does not match the proof target")
    if str(execution["proof_signal"]).upper() != normalized_signal:
        raise ValueError("probe execution signal does not match the proof signal")
    proof_channel = normalized_map[normalized_signal]
    expected_edge_count = _positive_int(
        execution["expected_edge_count"],
        field="probe execution expected_edge_count",
    )
    expected_interval = _positive_float(
        execution["interval_seconds"],
        field="probe execution interval_seconds",
    )
    proof_activity, edge_intervals = _validate_probe_capture_signature(
        Path(capture_path),
        proof_channel=proof_channel,
        expected_edge_count=expected_edge_count,
        expected_interval=expected_interval,
    )
    observed_edge_count = proof_activity.edge_count
    interval_tolerance = expected_interval * 0.35
    median_interval = float(median(edge_intervals))
    destination = Path(output_path)
    destination.write_text(
        json.dumps(
            {
                "target_host": target_host,
                "probe_host": probe_host,
                "trust_basis": "operator_correlated_host_toggle",
                "proof_signal": normalized_signal,
                "proof_channel": proof_channel,
                "command": execution["command"],
                "capture_path": str(capture_path),
                "capture_sha256": _sha256(Path(capture_path)),
                "execution_artifact": str(execution_path),
                "execution_sha256": _sha256(execution_path),
                "expected_edge_count": expected_edge_count,
                "observed_edge_count": observed_edge_count,
                "expected_edge_interval_seconds": expected_interval,
                "edge_interval_tolerance_seconds": interval_tolerance,
                "median_edge_interval_seconds": median_interval,
                "minimum_edge_interval_seconds": min(edge_intervals),
                "maximum_edge_interval_seconds": max(edge_intervals),
                "observed_channel": asdict(proof_activity),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return destination


def build_probe_toggle_command(
    *,
    target_host: str,
    gpio: int,
    toggles: int,
    interval_seconds: float,
) -> tuple[str, ...]:
    """Build the safe SSH command used to identify one host/probe channel."""

    if gpio < 0:
        raise ValueError(f"gpio must be non-negative, got {gpio}")
    if toggles <= 0:
        raise ValueError(f"toggles must be positive, got {toggles}")
    if interval_seconds <= 0:
        raise ValueError(
            f"interval_seconds must be positive, got {interval_seconds}"
        )
    if gpio != 17:
        raise ValueError(
            f"host proof currently requires the HUB75 CLK line on GPIO17, got {gpio}"
        )
    remote = (
        "set -eu; "
        "sudo -n pkill -TERM -f '[r]p1_hub75_run_candidate.sh' || true; "
        "sleep 0.2; "
        "if pgrep -f '[r]p1_hub75_run_candidate.sh' >/dev/null; then "
        "echo 'scanner still running' >&2; exit 1; fi; "
        f"trap 'sudo -n pinctrl set {gpio} no pn; "
        "sudo -n pinctrl set 18 op dh; sudo -n pinctrl set 4 op dh' EXIT; "
        "sudo -n pinctrl set 18 op dh; sudo -n pinctrl set 4 op dh; "
        f"sudo -n pinctrl set {gpio} op dl; "
        f"i=0; while [ \"$i\" -lt {toggles} ]; do "
        f"sudo -n pinctrl set {gpio} op dh; sleep {interval_seconds}; "
        f"sudo -n pinctrl set {gpio} op dl; sleep {interval_seconds}; "
        'i=$((i + 1)); done'
    )
    return ("ssh", target_host, remote)


def run_probe_toggle(
    *,
    target_host: str,
    proof_signal: str,
    gpio: int,
    toggles: int,
    interval_seconds: float,
    output_path: str | Path,
) -> Path:
    """Run and record one deliberate host toggle while Logic2 records."""

    if proof_signal.upper() != "CLK":
        raise ValueError("host proof currently requires proof_signal=CLK")
    command = build_probe_toggle_command(
        target_host=target_host,
        gpio=gpio,
        toggles=toggles,
        interval_seconds=interval_seconds,
    )
    started_at = datetime.now(UTC)
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    finished_at = datetime.now(UTC)
    if result.returncode != 0:
        raise RuntimeError(
            f"probe toggle failed with exit {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    destination = Path(output_path)
    destination.write_text(
        json.dumps(
            {
                "target_host": target_host,
                "proof_signal": proof_signal.upper(),
                "gpio": gpio,
                "toggles": toggles,
                "expected_edge_count": toggles * 2,
                "interval_seconds": interval_seconds,
                "safe_preconditions": [
                    "rp1_hub75_run_candidate.sh stopped and absence verified",
                    "active-low OE blanked high on GPIO18",
                    "legacy active-low OE blanked high on GPIO4",
                ],
                "cleanup": [
                    f"GPIO{gpio} restored to no/pn",
                    "GPIO18 left actively high/blank until the next retained run",
                    "GPIO4 left actively high/blank until the next retained run",
                ],
                "command": shlex.join(command),
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def render_virtual_image(
    capture_path: str | Path,
    output_path: str | Path,
    *,
    signal_map: Mapping[str, int],
    cols: int,
    rows: int,
    weight_oe: bool,
) -> Path:
    """Decode LAT commits into an approximate diagnostic panel image."""

    if rows <= 0 or rows % 2 or cols <= 0:
        raise ValueError("rows must be positive and even; cols must be positive")
    capture = load_hub75_logic_csv(capture_path, signal_map)
    missing = [signal for signal in REQUIRED_CAPTURE_SIGNALS if signal not in capture.signal_map]
    if missing:
        raise ValueError(
            f"virtual image requires signal mappings for: {', '.join(missing)}"
        )

    row_pairs = rows // 2
    accumulators = [
        [[0.0, 0.0, 0.0] for _column in range(cols)] for _row in range(rows)
    ]
    lat_rises = capture.rises[capture.signal_map["LAT"]]
    clk_rises = capture.rises[capture.signal_map["CLK"]]
    oe_falls = capture.falls[capture.signal_map["OE"]]
    oe_rises = capture.rises[capture.signal_map["OE"]]

    for lat_rise in lat_rises:
        end = bisect_left(clk_rises, lat_rise)
        start = end - cols
        if start < 0:
            continue
        clocks = clk_rises[start:end]
        row_pair = sum(
            capture.level_at(signal, lat_rise) << bit
            for bit, signal in enumerate(ADDRESS_SIGNALS)
            if signal in capture.signal_map
        )
        if row_pair >= row_pairs:
            continue
        weight = _oe_active_duration(
            lat_rise,
            oe_falls=oe_falls,
            oe_rises=oe_rises,
        )
        if not weight_oe:
            weight = 1.0
        for column, clock_rise in enumerate(clocks):
            sample_at = math.nextafter(clock_rise, -math.inf)
            for channel, signal in enumerate(COLOR_SIGNALS[:3]):
                accumulators[row_pair][column][channel] += (
                    capture.level_at(signal, sample_at) * weight
                )
            for channel, signal in enumerate(COLOR_SIGNALS[3:]):
                accumulators[row_pair + row_pairs][column][channel] += (
                    capture.level_at(signal, sample_at) * weight
                )

    maximum = max(
        (
            value
            for row in accumulators
            for pixel in row
            for value in pixel
        ),
        default=0.0,
    )
    if maximum <= 0:
        raise ValueError("capture contains no decodable color-channel activity")
    image = Image.new("RGB", (cols, rows))
    for row, accumulator_row in enumerate(accumulators):
        for column, pixel in enumerate(accumulator_row):
            image.putpixel(
                (column, row),
                tuple(round(255.0 * value / maximum) for value in pixel),
            )
    destination = Path(output_path)
    image.save(destination)
    return destination


@final
@dataclass(frozen=True)
class _CaptureProvenance:
    """Machine-checked proof identity attached only after preflight."""

    trust_basis: str
    target_host: str
    probe_host: str
    probe_proof: str
    probe_proof_sha256: str
    probe_capture_sha256: str
    execution_sha256: str
    saleae_module_name: str
    saleae_module_origin: str


@final
@dataclass(frozen=True)
class CapturePreflight:
    """Evidence required before a Logic2 capture can be trusted."""

    logic2_application: Path
    logic2_session_ready_attested: bool
    target_host: str
    probe_host: str
    probe_proof: Path

    def validate(self) -> _CaptureProvenance:
        """Reject the known session and host-routing failure modes."""

        return self._validate_saleae_module("saleae")

    def _validate_saleae_module(
        self,
        saleae_module_name: str,
    ) -> _CaptureProvenance:
        """Validate with an injected module name only for focused tests."""

        if not self.logic2_application.exists():
            raise ValueError(
                f"Logic2 preflight failed; application not found: "
                f"{self.logic2_application}"
            )
        if not self.logic2_session_ready_attested:
            raise ValueError(
                "Logic2 preflight failed; stop or close the active recording "
                "before switching capture sessions"
            )
        saleae_module_origin = _saleae_module_origin(saleae_module_name)
        if saleae_module_origin is None:
            raise ValueError(
                "Logic2 preflight failed; Saleae automation support is unavailable"
            )
        normalized_target = _normalize_host_identity(self.target_host)
        normalized_probe = _normalize_host_identity(self.probe_host)
        if not normalized_target or not normalized_probe:
            raise ValueError("target_host and probe_host must both be explicit")
        if normalized_target != normalized_probe:
            raise ValueError(
                f"probe host {self.probe_host!r} does not match target host "
                f"{self.target_host!r}"
            )
        proof = _load_probe_proof(self.probe_proof)
        if _normalize_host_identity(str(proof.get("target_host", ""))) != normalized_target:
            raise ValueError("probe proof target_host does not match the capture target")
        if _normalize_host_identity(str(proof.get("probe_host", ""))) != normalized_probe:
            raise ValueError("probe proof probe_host does not match the capture probe")
        observed_edge_count = proof.get("observed_edge_count")
        if not isinstance(observed_edge_count, int) or observed_edge_count <= 0:
            raise ValueError(
                "probe proof must record at least one deliberate observed edge"
            )
        if not str(proof.get("command", "")).strip():
            raise ValueError("probe proof must record the deliberate toggle command")
        return _CaptureProvenance(
            trust_basis=str(proof["trust_basis"]),
            target_host=normalized_target,
            probe_host=normalized_probe,
            probe_proof=str(self.probe_proof),
            probe_proof_sha256=_sha256(self.probe_proof),
            probe_capture_sha256=str(proof["capture_sha256"]),
            execution_sha256=str(proof["execution_sha256"]),
            saleae_module_name=saleae_module_name,
            saleae_module_origin=saleae_module_origin,
        )


@final
@dataclass(frozen=True)
class CaptureReport:
    """Electrical evidence for one host-proven Logic2 capture."""

    path: Path
    capture_sha256: str
    target_host: str
    probe_host: str
    diagnosis: Hub75CaptureDiagnosis
    control_edge_counts: dict[str, int]
    address_edge_counts: dict[str, int | None]
    color_edge_counts: dict[str, int | None]
    color_evidence: dict[str, SignalEvidence | None]
    missing_color_signals: tuple[str, ...]
    missing_required_signals: tuple[str, ...]
    expected_active_colors: tuple[str, ...]
    provenance: _CaptureProvenance | None

    @property
    def color_pattern_valid(self) -> bool:
        """Return whether mapped color evidence matches the declared pattern."""

        if self.missing_color_signals:
            return False
        if self.expected_active_colors:
            expected = set(self.expected_active_colors)
            expected_valid = all(
                _signal_has_activity(self.color_evidence[signal])
                for signal in expected
            )
            inactive_valid = all(
                _signal_is_static_low(self.color_evidence[signal])
                for signal in set(COLOR_SIGNALS) - expected
            )
            return expected_valid and inactive_valid
        return all(
            evidence is not None
            and evidence.edge_count == 0
            and evidence.initial_level == 0
            and evidence.final_level == 0
            for evidence in self.color_evidence.values()
        )

    @property
    def is_trusted(self) -> bool:
        """Return whether this capture may be used as comparison evidence."""

        return (
            self.provenance is not None
            and self.diagnosis.summary.valid_hub75
            and self.diagnosis.diagnosis == "valid_hub75"
            and bool(self.diagnosis.active_channels)
            and not self.missing_required_signals
            and self.color_pattern_valid
        )

    def require_trusted(self) -> None:
        """Fail closed when diagnostic evidence is incomplete or silent."""

        if self.is_trusted:
            return
        problems: list[str] = []
        if self.provenance is None:
            problems.append("capture has no validated probe provenance")
        if self.diagnosis.diagnosis == "electrically_silent":
            problems.append("capture is electrically silent")
        elif not self.diagnosis.summary.valid_hub75:
            problems.append(
                f"invalid HUB75 waveform: "
                f"{', '.join(self.diagnosis.summary.validity_issues)}"
            )
        if self.missing_required_signals:
            problems.append(
                f"missing required signal mappings: "
                f"{', '.join(self.missing_required_signals)}"
            )
        unmapped_colors = [
            signal
            for signal, count in self.color_edge_counts.items()
            if count is None
        ]
        if unmapped_colors:
            problems.append(
                f"missing color-channel evidence for: {', '.join(unmapped_colors)}"
            )
        elif not self.color_pattern_valid:
            declared = ", ".join(self.expected_active_colors) or "black/static-low"
            problems.append(f"color evidence does not match declared pattern {declared}")
        raise ValueError(
            "capture is diagnostic-only and cannot be comparison evidence; "
            + "; ".join(problems)
        )


@final
@dataclass(frozen=True)
class SignalEvidence:
    """Edge and static-level evidence for one mapped signal."""

    edge_count: int
    edges_per_lat_interval: float | None
    initial_level: int
    final_level: int


@final
@dataclass(frozen=True)
class CompleteSimilarityScore:
    """Full comparison including control/timing/address and RGB evidence."""

    overall_similarity: float
    control_timing_address_similarity: float
    color_similarity: float
    color_channel_similarity: dict[str, float]
    compared_color_signals: tuple[str, ...]
    control_timing_address_weight: float
    color_weight: float
    pass_threshold: float
    verdict: str


def _load_probe_proof(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"probe proof artifact does not exist: {path}")
    try:
        parsed: object = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid probe proof artifact {path}: {error}") from error
    if not isinstance(parsed, dict):
        raise ValueError(f"probe proof artifact must contain a JSON object: {path}")
    payload = cast(dict[str, object], parsed)
    capture_path = Path(str(payload.get("capture_path", "")))
    if not capture_path.is_file():
        raise ValueError(f"probe proof source CSV does not exist: {capture_path}")
    expected_sha = payload.get("capture_sha256")
    if not isinstance(expected_sha, str) or expected_sha != _sha256(capture_path):
        raise ValueError("probe proof source CSV hash does not match the artifact")
    if payload.get("trust_basis") != "operator_correlated_host_toggle":
        raise ValueError("probe proof has no accepted execution/capture correlation")
    observed_channel = payload.get("observed_channel")
    if not isinstance(observed_channel, dict):
        raise ValueError("probe proof must identify the observed proof channel")
    if payload.get("proof_signal") != "CLK":
        raise ValueError("probe proof did not use the required safe CLK signal")
    if not isinstance(payload.get("median_edge_interval_seconds"), float):
        raise ValueError("probe proof does not record cadence evidence")
    execution_path = Path(str(payload.get("execution_artifact", "")))
    if not execution_path.is_file():
        raise ValueError("probe proof execution artifact does not exist")
    if payload.get("execution_sha256") != _sha256(execution_path):
        raise ValueError("probe proof execution artifact hash does not match")
    execution = _load_probe_execution(execution_path)
    proof_target = _normalize_host_identity(str(payload.get("target_host", "")))
    proof_probe = _normalize_host_identity(str(payload.get("probe_host", "")))
    execution_target = _normalize_host_identity(str(execution["target_host"]))
    if not proof_target or proof_target != proof_probe:
        raise ValueError("probe proof target and probe host labels do not match")
    if proof_target != execution_target:
        raise ValueError("probe proof target does not match the execution transcript")
    proof_signal = str(payload.get("proof_signal", "")).upper()
    execution_signal = str(execution["proof_signal"]).upper()
    if proof_signal != execution_signal:
        raise ValueError("probe proof signal does not match the execution transcript")
    expected_edge_count = _positive_int(
        payload.get("expected_edge_count"),
        field="probe proof expected_edge_count",
    )
    execution_edge_count = _positive_int(
        execution["expected_edge_count"],
        field="probe execution expected_edge_count",
    )
    if expected_edge_count != execution_edge_count:
        raise ValueError(
            "probe proof expected edge count does not match the execution transcript"
        )
    expected_interval = _positive_float(
        payload.get("expected_edge_interval_seconds"),
        field="probe proof expected_edge_interval_seconds",
    )
    execution_interval = _positive_float(
        execution["interval_seconds"],
        field="probe execution interval_seconds",
    )
    if not math.isclose(expected_interval, execution_interval):
        raise ValueError(
            "probe proof cadence does not match the execution transcript"
        )
    if payload.get("command") != execution["command"]:
        raise ValueError("probe proof command does not match the execution transcript")
    proof_channel = _nonnegative_int(
        payload.get("proof_channel"),
        field="probe proof proof_channel",
    )
    activity, edge_intervals = _validate_probe_capture_signature(
        capture_path,
        proof_channel=proof_channel,
        expected_edge_count=expected_edge_count,
        expected_interval=expected_interval,
    )
    if payload.get("observed_edge_count") != activity.edge_count:
        raise ValueError("probe proof observed edge count does not match its source CSV")
    if (
        observed_channel.get("channel") != activity.channel
        or observed_channel.get("edge_count") != activity.edge_count
    ):
        raise ValueError("probe proof observed channel does not match its source CSV")
    expected_cadence_evidence = {
        "edge_interval_tolerance_seconds": expected_interval * 0.35,
        "median_edge_interval_seconds": float(median(edge_intervals)),
        "minimum_edge_interval_seconds": min(edge_intervals),
        "maximum_edge_interval_seconds": max(edge_intervals),
    }
    for field, expected_value in expected_cadence_evidence.items():
        observed_value = _positive_float(
            payload.get(field),
            field=f"probe proof {field}",
            allow_zero=True,
        )
        if not math.isclose(observed_value, expected_value):
            raise ValueError(
                f"probe proof {field} does not match its source CSV"
            )
    return payload


def _normalize_host_identity(host: str) -> str:
    return host.strip().split("@", maxsplit=1)[-1].lower()


def _saleae_support_available(module_name: str = "saleae") -> bool:
    return _saleae_module_origin(module_name) is not None


def _saleae_module_origin(module_name: str) -> str | None:
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ModuleNotFoundError, ValueError):
        return None
    if spec is None or spec.origin is None:
        return None
    return spec.origin


def _oe_active_duration(
    lat_rise: float,
    *,
    oe_falls: list[float],
    oe_rises: list[float],
) -> float:
    fall_index = bisect_right(oe_falls, lat_rise)
    if fall_index >= len(oe_falls):
        return 0.0
    active_start = oe_falls[fall_index]
    rise_index = bisect_right(oe_rises, active_start)
    if rise_index >= len(oe_rises):
        return 0.0
    return max(oe_rises[rise_index] - active_start, 0.0)


def _signal_evidence(
    capture: Any,
    signal: str,
) -> SignalEvidence | None:
    if signal not in capture.signal_map:
        return None
    channel = capture.signal_map[signal]
    edge_count = len(capture.edges[channel])
    initial_level = capture.initial_state[channel]
    lat_rises = capture.rises[capture.signal_map["LAT"]]
    return SignalEvidence(
        edge_count=edge_count,
        edges_per_lat_interval=_edges_per_lat_interval(
            capture.edges[channel],
            lat_rises,
        ),
        initial_level=initial_level,
        final_level=initial_level ^ (edge_count & 1),
    )


def _edges_per_lat_interval(
    edges: list[float],
    lat_rises: list[float],
) -> float | None:
    if len(lat_rises) < 2:
        return None
    complete_interval_edges = bisect_left(edges, lat_rises[-1]) - bisect_right(
        edges,
        lat_rises[0],
    )
    return complete_interval_edges / (len(lat_rises) - 1)


def _signal_has_activity(evidence: SignalEvidence | None) -> bool:
    return evidence is not None and (
        evidence.edge_count > 0
        or evidence.initial_level == 1
        or evidence.final_level == 1
    )


def _signal_is_static_low(evidence: SignalEvidence | None) -> bool:
    return (
        evidence is not None
        and evidence.edge_count == 0
        and evidence.initial_level == 0
        and evidence.final_level == 0
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def score_complete_similarity(
    baseline: CaptureReport,
    candidate: CaptureReport,
    control_timing_address: Hub75SimilarityScore,
) -> CompleteSimilarityScore:
    """Combine normalized waveform similarity with explicit RGB evidence."""

    color_channel_similarity = {
        signal: _signal_evidence_similarity(
            baseline.color_evidence[signal],
            candidate.color_evidence[signal],
        )
        for signal in COLOR_SIGNALS
    }
    compared_color_signals = tuple(
        signal
        for signal in COLOR_SIGNALS
        if _signal_has_activity(baseline.color_evidence[signal])
        or _signal_has_activity(candidate.color_evidence[signal])
    )
    if not compared_color_signals:
        compared_color_signals = COLOR_SIGNALS
    color_similarity = sum(
        color_channel_similarity[signal] for signal in compared_color_signals
    ) / len(compared_color_signals)
    overall_similarity = (
        control_timing_address.total * COMPLETE_SIMILARITY_CONTROL_WEIGHT
        + color_similarity * COMPLETE_SIMILARITY_COLOR_WEIGHT
    )
    verdict = (
        "pass"
        if baseline.is_trusted
        and candidate.is_trusted
        and overall_similarity >= COMPLETE_SIMILARITY_PASS_THRESHOLD
        else "fail"
    )
    return CompleteSimilarityScore(
        overall_similarity=overall_similarity,
        control_timing_address_similarity=control_timing_address.total,
        color_similarity=color_similarity,
        color_channel_similarity=color_channel_similarity,
        compared_color_signals=compared_color_signals,
        control_timing_address_weight=COMPLETE_SIMILARITY_CONTROL_WEIGHT,
        color_weight=COMPLETE_SIMILARITY_COLOR_WEIGHT,
        pass_threshold=COMPLETE_SIMILARITY_PASS_THRESHOLD,
        verdict=verdict,
    )


def _signal_evidence_similarity(
    baseline: SignalEvidence | None,
    candidate: SignalEvidence | None,
) -> float:
    if baseline is None or candidate is None:
        return 0.0
    if baseline.edge_count == 0 and candidate.edge_count == 0:
        return (
            1.0
            if baseline.initial_level == candidate.initial_level
            and baseline.final_level == candidate.final_level
            else 0.0
        )
    if (baseline.edge_count > 0) != (candidate.edge_count > 0):
        return 0.0
    baseline_rate = baseline.edges_per_lat_interval
    candidate_rate = candidate.edges_per_lat_interval
    if baseline_rate is None or candidate_rate is None:
        return 0.0
    maximum_rate = max(baseline_rate, candidate_rate)
    return (
        1.0
        if maximum_rate == 0.0
        else 1.0 - abs(baseline_rate - candidate_rate) / maximum_rate
    )


def _load_probe_execution(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"probe execution artifact does not exist: {path}")
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid probe execution artifact {path}: {error}") from error
    if not isinstance(parsed, dict):
        raise ValueError(
            f"probe execution artifact must contain a JSON object: {path}"
        )
    payload = cast(dict[str, object], parsed)
    required = (
        "target_host",
        "proof_signal",
        "command",
        "expected_edge_count",
        "interval_seconds",
        "safe_preconditions",
        "cleanup",
        "started_at",
        "finished_at",
        "returncode",
    )
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(
            f"probe execution artifact is missing: {', '.join(missing)}"
        )
    if payload["returncode"] != 0:
        raise ValueError("probe execution artifact records a failed command")
    if not str(payload["target_host"]).strip():
        raise ValueError("probe execution target_host must be explicit")
    if str(payload["proof_signal"]).upper() != "CLK":
        raise ValueError("probe execution must use the safe CLK proof signal")
    _positive_int(
        payload["expected_edge_count"],
        field="probe execution expected_edge_count",
    )
    _positive_float(
        payload["interval_seconds"],
        field="probe execution interval_seconds",
    )
    command = str(payload["command"])
    required_command_fragments = (
        "[r]p1_hub75_run_candidate.sh",
        "pinctrl set 18 op dh",
        "pinctrl set 4 op dh",
        "pinctrl set 17",
    )
    missing_fragments = [
        fragment for fragment in required_command_fragments if fragment not in command
    ]
    if missing_fragments:
        raise ValueError(
            "probe execution command is missing safe host-toggle operations: "
            + ", ".join(missing_fragments)
        )
    cleanup = payload["cleanup"]
    if not isinstance(cleanup, list) or not all(
        any(pin in str(item) for item in cleanup)
        for pin in ("GPIO17", "GPIO18", "GPIO4")
    ):
        raise ValueError("probe execution cleanup does not cover CLK and both OE pins")
    if not all(
        any(
            pin in str(item) and "high/blank" in str(item)
            for item in cleanup
        )
        for pin in ("GPIO18", "GPIO4")
    ):
        raise ValueError("probe execution cleanup must leave both OE pins high/blank")
    return payload


def _validate_probe_capture_signature(
    capture_path: Path,
    *,
    proof_channel: int,
    expected_edge_count: int,
    expected_interval: float,
) -> tuple[LogicChannelActivity, tuple[float, ...]]:
    activities = summarize_logic_channels(capture_path)
    proof_activity = next(
        (activity for activity in activities if activity.channel == proof_channel),
        None,
    )
    observed_edge_count = 0 if proof_activity is None else proof_activity.edge_count
    if abs(observed_edge_count - expected_edge_count) > 1:
        raise ValueError(
            f"proof channel {proof_channel} for CLK observed "
            f"{observed_edge_count} edges; expected {expected_edge_count} +/- 1"
        )
    if proof_activity is None:
        raise ValueError(f"proof capture has no channel {proof_channel}")
    capture = load_hub75_logic_csv(capture_path, {"CLK": proof_channel})
    proof_edges = capture.edges[proof_channel]
    edge_intervals = tuple(
        later - earlier
        for earlier, later in zip(proof_edges, proof_edges[1:], strict=False)
    )
    interval_tolerance = expected_interval * 0.35
    if not edge_intervals or any(
        abs(interval - expected_interval) > interval_tolerance
        for interval in edge_intervals
    ):
        raise ValueError(
            f"proof channel {proof_channel} does not match the deliberate "
            f"{expected_interval:.6f}s toggle cadence"
        )
    return proof_activity, edge_intervals


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _positive_float(
    value: object,
    *,
    field: str,
    allow_zero: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    resolved = float(value)
    minimum_is_valid = resolved >= 0 if allow_zero else resolved > 0
    if not math.isfinite(resolved) or not minimum_is_valid:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{field} must be a finite {qualifier} number")
    return resolved
