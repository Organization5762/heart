"""Public command-line interface for the consolidated HUB75 laboratory."""

from __future__ import annotations

import argparse
import json
import shlex
from dataclasses import asdict
from pathlib import Path
from typing import Any

from heart.utilities.hub75_lab._bundle import main as bundle_main
from heart.utilities.hub75_lab._execution import (ExperimentCommand,
                                                  run_experiment_command)
from heart.utilities.hub75_lab.capture import (DEFAULT_CAPTURE_SIGNAL_MAP,
                                               CapturePreflight,
                                               analyze_capture,
                                               capture_report_payload,
                                               create_probe_proof,
                                               render_virtual_image,
                                               run_probe_toggle,
                                               score_complete_similarity)
from heart.utilities.hub75_lab.experiments import (APPLIED_SETTING_NAMES,
                                                   ExperimentSettings,
                                                   build_experiment_command,
                                                   list_experiments)
from heart.utilities.hub75_lab.memory import validate_sram_buffer
from heart.utilities.hub75_logic_score import score_hub75_capture_files

REPO_ROOT = Path(__file__).resolve().parents[4]
INVENTORY_PATH = REPO_ROOT / "docs" / "hub75_script_inventory.json"
DEFAULT_LOGIC2_APPLICATION = Path("/Applications/Logic 2.app")
EXPERIMENTS = list_experiments()
EXPERIMENT_NAMES = tuple(experiment.name for experiment in EXPERIMENTS)


def main(argv: list[str] | None = None) -> int:
    """Run the consolidated HUB75 laboratory CLI."""

    args = _build_parser().parse_args(argv)
    if args.command == "list":
        return _list_command(args)
    if args.command in ("plan", "run"):
        return _experiment_command(args)
    if args.command == "inventory":
        return _inventory_command()
    if args.command == "validate-sram":
        return _validate_sram_command(args)
    if args.command == "probe-proof":
        return _probe_proof_command(args)
    if args.command == "probe-toggle":
        return _probe_toggle_command(args)
    if args.command == "capture":
        return _capture_command(args)
    if args.command == "score":
        return _score_command(args)
    if args.command == "render-capture":
        return _render_capture_command(args)
    if args.command == "bundle":
        return _bundle_command(args)
    raise AssertionError(args.command)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan, run, capture, score, and deploy retained HUB75 experiments. "
            "No temporal-PWM control is exposed."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List retained experiments.")
    list_parser.add_argument("--json", action="store_true")

    settings_parent = argparse.ArgumentParser(add_help=False)
    _add_experiment_settings(settings_parent)
    for command in ("plan", "run"):
        experiment_parser = subparsers.add_parser(
            command,
            parents=[settings_parent],
            help=f"{command.title()} one retained experiment.",
        )
        experiment_parser.add_argument("experiment", choices=EXPERIMENT_NAMES)

    subparsers.add_parser(
        "inventory",
        help="Print the machine-checkable 27-script inventory.",
    )

    sram_parser = subparsers.add_parser(
        "validate-sram",
        help="Validate one shared-SRAM source range before deployment.",
    )
    sram_parser.add_argument("--payload-size", type=_integer, required=True)
    sram_parser.add_argument("--source-offset", type=_integer, required=True)
    sram_parser.add_argument("--source-size", type=_integer, required=True)
    sram_parser.add_argument("--alignment", type=_integer, default=4)

    proof_parser = subparsers.add_parser(
        "probe-proof",
        help="Correlate a runner toggle transcript with a named capture channel.",
    )
    proof_parser.add_argument("capture_csv", type=Path)
    proof_parser.add_argument("--target-host", required=True)
    proof_parser.add_argument("--probe-host", required=True)
    proof_parser.add_argument("--proof-signal", required=True)
    proof_parser.add_argument("--execution-artifact", type=Path, required=True)
    proof_parser.add_argument("--output", type=Path, required=True)
    _add_signal_args(proof_parser)

    toggle_parser = subparsers.add_parser(
        "probe-toggle",
        help=(
            "Toggle CLK while Logic2 records, save a transcript, and leave both "
            "OE candidates actively blank."
        ),
    )
    toggle_parser.add_argument("--target-host", required=True)
    toggle_parser.add_argument("--proof-signal", required=True)
    toggle_parser.add_argument("--gpio", type=int, required=True)
    toggle_parser.add_argument("--toggles", type=int, default=4)
    toggle_parser.add_argument("--interval-seconds", type=float, default=0.05)
    toggle_parser.add_argument("--output", type=Path, required=True)

    capture_parser = subparsers.add_parser(
        "capture",
        help="Preflight and accept or diagnose one exported Logic2 capture.",
    )
    capture_parser.add_argument("capture_csv", type=Path)
    _add_capture_evidence_args(capture_parser, include_expected_colors=True)
    capture_parser.add_argument(
        "--diagnostic-only",
        action="store_true",
        help="Return incomplete evidence instead of failing closed.",
    )

    score_parser = subparsers.add_parser(
        "score",
        help="Compare two trusted captures with OE and color evidence.",
    )
    score_parser.add_argument("baseline", type=Path)
    score_parser.add_argument("candidate", type=Path)
    _add_capture_evidence_args(score_parser, include_expected_colors=False)
    score_parser.add_argument(
        "--baseline-expected-colors",
        default="R1,R2",
        help="Expected active color signals, or 'none' for a black pattern.",
    )
    score_parser.add_argument(
        "--candidate-expected-colors",
        default="R1,R2",
        help="Expected active color signals, or 'none' for a black pattern.",
    )

    render_parser = subparsers.add_parser(
        "render-capture",
        help="Render an approximate diagnostic image from a Logic2 CSV.",
    )
    render_parser.add_argument("capture_csv", type=Path)
    render_parser.add_argument("--output", type=Path, required=True)
    render_parser.add_argument("--cols", type=int, default=64)
    render_parser.add_argument("--rows", type=int, default=64)
    render_parser.add_argument("--weight-oe", action="store_true")
    _add_signal_args(render_parser)

    bundle_parser = subparsers.add_parser(
        "bundle",
        help="Delegate to the retained Heart-owned Linux bundle manager.",
    )
    bundle_parser.add_argument(
        "bundle_args",
        nargs=argparse.REMAINDER,
        help="Arguments for rp1_hub75_linux_bundle.py.",
    )
    return parser


def _add_experiment_settings(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", default="michael@totem3.local")
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--cols", type=int, default=64)
    parser.add_argument("--chain-length", type=int, default=1)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument(
        "--hardware-mapping",
        choices=("adafruit-hat", "adafruit-hat-pwm"),
        default="adafruit-hat-pwm",
    )
    parser.add_argument("--led-rgb-sequence", default="RGB")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--pwm-bits", type=int, default=6)
    parser.add_argument(
        "--candidate",
        default=(
            "state32-regular-p0p1-chain2-oeoffshift-preclk1-"
            "unroll8-addr8-lat2"
        ),
    )
    parser.add_argument("--frame-slot-offset", type=_integer, default=0xB800)
    parser.add_argument(
        "--strict-hashes",
        action="store_true",
        help="Additionally enforce known-good module srcversion and SHA-256.",
    )
    parser.add_argument("--intensities", default="32,96,160,255")
    parser.add_argument("--row-index", type=int, default=0)
    parser.add_argument("--line-thickness", type=int, default=1)
    parser.add_argument("--red", type=int, default=255)
    parser.add_argument("--green", type=int, default=255)
    parser.add_argument("--blue", type=int, default=255)
    parser.add_argument("--row-dwell-seconds", type=float, default=0.0005)
    parser.add_argument(
        "--gpio-diagnostic-mode",
        choices=("scan", "hold-row", "latch-pulse", "walking-bit"),
        default="scan",
    )


def _add_capture_evidence_args(
    parser: argparse.ArgumentParser,
    *,
    include_expected_colors: bool,
) -> None:
    parser.add_argument("--cols", type=int, default=64)
    parser.add_argument("--target-host", required=True)
    parser.add_argument("--probe-host", required=True)
    parser.add_argument("--probe-proof", type=Path, required=True)
    parser.add_argument(
        "--logic2-application",
        type=Path,
        default=DEFAULT_LOGIC2_APPLICATION,
    )
    parser.add_argument(
        "--attest-logic2-session-ready",
        action="store_true",
        help=(
            "Operator attestation that Logic2 is available and no recording session "
            "is blocking capture switching. Saleae Python support is checked."
        ),
    )
    if include_expected_colors:
        parser.add_argument(
            "--expected-colors",
            default="R1,R2",
            help="Expected active color signals, or 'none' for a black pattern.",
        )
    _add_signal_args(parser)


def _add_signal_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--signal",
        action="append",
        default=[],
        metavar="NAME=CHANNEL",
        help=(
            "Override the documented connector map. Repeat for multiple signals; "
            "the resolved CLK/LAT/OE/A-D/R1/G1/B1/R2/G2/B2 map is printed."
        ),
    )


def _list_command(args: argparse.Namespace) -> int:
    if args.json:
        print(
            json.dumps(
                [
                    {
                        **asdict(experiment),
                        "applied_parameters": list(
                            APPLIED_SETTING_NAMES[experiment.name]
                        ),
                    }
                    for experiment in EXPERIMENTS
                ],
                indent=2,
            )
        )
        return 0
    for experiment in EXPERIMENTS:
        print(f"{experiment.name}: {experiment.summary}")
    return 0


def _experiment_command(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    command = build_experiment_command(
        repo_root=REPO_ROOT,
        name=args.experiment,
        settings=settings,
    )
    payload = _experiment_payload(args.experiment, command)
    if args.command == "plan":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(json.dumps(payload, indent=2, sort_keys=True))
    run_experiment_command(command)
    return 0


def _inventory_command() -> int:
    print(INVENTORY_PATH.read_text(), end="")
    return 0


def _validate_sram_command(args: argparse.Namespace) -> int:
    layout = validate_sram_buffer(
        payload_size=args.payload_size,
        source_offset=args.source_offset,
        source_size=args.source_size,
        required_alignment=args.alignment,
    )
    print(json.dumps(asdict(layout), indent=2, sort_keys=True))
    return 0


def _probe_proof_command(args: argparse.Namespace) -> int:
    path = create_probe_proof(
        args.capture_csv,
        target_host=args.target_host,
        probe_host=args.probe_host,
        proof_signal=args.proof_signal,
        signal_map=_parse_signal_map(args.signal),
        execution_artifact=args.execution_artifact,
        output_path=args.output,
    )
    print(path)
    return 0


def _probe_toggle_command(args: argparse.Namespace) -> int:
    path = run_probe_toggle(
        target_host=args.target_host,
        proof_signal=args.proof_signal,
        gpio=args.gpio,
        toggles=args.toggles,
        interval_seconds=args.interval_seconds,
        output_path=args.output,
    )
    print(path)
    return 0


def _capture_command(args: argparse.Namespace) -> int:
    report = analyze_capture(
        args.capture_csv,
        preflight=_capture_preflight(args),
        signal_map=_parse_signal_map(args.signal),
        cols=args.cols,
        expected_active_colors=_parse_expected_colors(args.expected_colors),
        require_trusted=not args.diagnostic_only,
    )
    payload = capture_report_payload(report)
    payload["resolved_signal_map"] = _parse_signal_map(args.signal)
    payload["logic2_session_ready"] = {
        "value": args.attest_logic2_session_ready,
        "source": "operator_attestation",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _score_command(args: argparse.Namespace) -> int:
    signal_map = _parse_signal_map(args.signal)
    preflight = _capture_preflight(args)
    baseline_report = analyze_capture(
        args.baseline,
        preflight=preflight,
        signal_map=signal_map,
        cols=args.cols,
        expected_active_colors=_parse_expected_colors(
            args.baseline_expected_colors
        ),
    )
    candidate_report = analyze_capture(
        args.candidate,
        preflight=preflight,
        signal_map=signal_map,
        cols=args.cols,
        expected_active_colors=_parse_expected_colors(
            args.candidate_expected_colors
        ),
    )
    _baseline, _candidate, score = score_hub75_capture_files(
        args.baseline,
        args.candidate,
        signal_map=signal_map,
        cols=args.cols,
    )
    complete_score = score_complete_similarity(
        baseline_report,
        candidate_report,
        score,
    )
    print(
        json.dumps(
            {
                "baseline": capture_report_payload(baseline_report),
                "candidate": capture_report_payload(candidate_report),
                "similarity": asdict(complete_score),
                "control_timing_address_detail": asdict(score),
                "resolved_signal_map": signal_map,
                "logic2_session_ready": {
                    "value": args.attest_logic2_session_ready,
                    "source": "operator_attestation",
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _render_capture_command(args: argparse.Namespace) -> int:
    destination = render_virtual_image(
        args.capture_csv,
        args.output,
        signal_map=_parse_signal_map(args.signal),
        cols=args.cols,
        rows=args.rows,
        weight_oe=args.weight_oe,
    )
    print(destination)
    return 0


def _bundle_command(args: argparse.Namespace) -> int:
    return bundle_main(args.bundle_args)


def _settings_from_args(args: argparse.Namespace) -> ExperimentSettings:
    return ExperimentSettings(
        target=args.target,
        rows=args.rows,
        cols=args.cols,
        chain_length=args.chain_length,
        parallel=args.parallel,
        hardware_mapping=args.hardware_mapping,
        led_rgb_sequence=args.led_rgb_sequence,
        seconds=args.seconds,
        pwm_bits=args.pwm_bits,
        candidate=args.candidate,
        frame_slot_offset=args.frame_slot_offset,
        strict_hashes=args.strict_hashes,
        intensities=args.intensities,
        row_index=args.row_index,
        line_thickness=args.line_thickness,
        red=args.red,
        green=args.green,
        blue=args.blue,
        row_dwell_seconds=args.row_dwell_seconds,
        gpio_diagnostic_mode=args.gpio_diagnostic_mode,
    )


def _experiment_payload(
    name: str,
    command: ExperimentCommand,
) -> dict[str, Any]:
    return {
        "experiment": name,
        "applied_settings": command.applied_settings,
        "fixed_invariants": command.fixed_invariants,
        "command": {
            "argv": list(command.argv),
            "shell": shlex.join(command.argv),
            "environment": command.environment,
            "cwd": str(command.cwd),
        },
        "safety_evidence": list(command.safety_evidence),
    }


def _capture_preflight(args: argparse.Namespace) -> CapturePreflight:
    return CapturePreflight(
        logic2_application=args.logic2_application,
        logic2_session_ready_attested=args.attest_logic2_session_ready,
        target_host=args.target_host,
        probe_host=args.probe_host,
        probe_proof=args.probe_proof,
    )


def _parse_signal_map(overrides: list[str]) -> dict[str, int]:
    signal_map = DEFAULT_CAPTURE_SIGNAL_MAP.copy()
    allowed_names = {
        "CLK",
        "LAT",
        "OE",
        "A",
        "B",
        "C",
        "D",
        "E",
        "R1",
        "G1",
        "B1",
        "R2",
        "G2",
        "B2",
    }
    for raw_override in overrides:
        name, separator, raw_channel = raw_override.partition("=")
        normalized_name = name.strip().upper()
        if not separator or not normalized_name:
            raise ValueError(
                f"invalid signal override {raw_override!r}; expected NAME=CHANNEL"
            )
        if normalized_name not in allowed_names:
            raise ValueError(
                f"unknown HUB75 signal {normalized_name!r} in {raw_override!r}"
            )
        try:
            channel = int(raw_channel, 0)
        except ValueError as error:
            raise ValueError(
                f"invalid channel in signal override {raw_override!r}"
            ) from error
        if channel < 0:
            raise ValueError(
                f"signal channel must be non-negative in {raw_override!r}"
            )
        signal_map[normalized_name] = channel
    assignments: dict[int, str] = {}
    for name, channel in signal_map.items():
        previous = assignments.get(channel)
        if previous is not None:
            raise ValueError(
                f"HUB75 signals {previous} and {name} both map to channel {channel}"
            )
        assignments[channel] = name
    return signal_map


def _parse_expected_colors(raw_colors: str) -> tuple[str, ...]:
    if raw_colors.strip().lower() == "none":
        return ()
    colors = tuple(
        component.strip().upper()
        for component in raw_colors.split(",")
        if component.strip()
    )
    if not colors:
        raise ValueError("expected colors must be signal names or 'none'")
    return colors


def _integer(raw_value: str) -> int:
    return int(raw_value, 0)


if __name__ == "__main__":
    raise SystemExit(main())
