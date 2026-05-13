"""Score one HUB75 logic CSV against another."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from heart.utilities.hub75_logic_score import score_hub75_capture_files
from heart.utilities.hub75_logic_score import diagnose_hub75_capture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", help="baseline Saleae raw digital CSV export")
    parser.add_argument("candidate", help="candidate Saleae raw digital CSV export")
    parser.add_argument("--cols", type=int, default=64)
    parser.add_argument(
        "--signal",
        action="append",
        default=[],
        metavar="NAME=CHANNEL",
        help="Override one HUB75 signal mapping entry, for example --signal CLK=9.",
    )
    args = parser.parse_args()
    signal_map = _parse_signal_map(args.signal)

    baseline, candidate, score = score_hub75_capture_files(
        args.baseline,
        args.candidate,
        signal_map=signal_map,
        cols=args.cols,
    )
    baseline_diagnosis = diagnose_hub75_capture(
        args.baseline,
        signal_map=signal_map,
        cols=args.cols,
    )
    candidate_diagnosis = diagnose_hub75_capture(
        args.candidate,
        signal_map=signal_map,
        cols=args.cols,
    )
    payload = {
        "signal_map": dict(sorted((signal_map or {}).items())),
        "baseline": _summary_payload(baseline),
        "baseline_diagnosis": _diagnosis_payload(baseline_diagnosis),
        "candidate": _summary_payload(candidate),
        "candidate_diagnosis": _diagnosis_payload(candidate_diagnosis),
        "score": {
            "total": round(score.total, 6),
            "control_similarity": round(score.control_similarity, 6),
            "timing_similarity": round(score.timing_similarity, 6),
            "address_similarity": round(score.address_similarity, 6),
            "feature_scores": {
                key: round(value, 6) for key, value in sorted(score.feature_scores.items())
            },
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _parse_signal_map(overrides: list[str]) -> dict[str, int] | None:
    signal_map: dict[str, int] = {}
    for override in overrides:
        name, separator, channel_text = override.partition("=")
        if not separator:
            msg = f"invalid --signal override {override!r}; expected NAME=CHANNEL"
            raise SystemExit(msg)
        signal_name = name.strip().upper()
        if not signal_name:
            msg = f"invalid --signal override {override!r}; missing signal name"
            raise SystemExit(msg)
        try:
            channel = int(channel_text.strip(), 0)
        except ValueError as error:
            msg = f"invalid --signal override {override!r}; channel must be an integer"
            raise SystemExit(msg) from error
        signal_map[signal_name] = channel
    return signal_map or None


def _summary_payload(summary: object) -> dict[str, object]:
    summary_dict = summary.__dict__.copy()
    summary_dict["address_edges_per_lat"] = dict(
        sorted(summary_dict["address_edges_per_lat"].items())
    )
    return summary_dict


def _diagnosis_payload(diagnosis: object) -> dict[str, object]:
    return {
        "diagnosis": diagnosis.diagnosis,
        "channel_activity": [activity.__dict__.copy() for activity in diagnosis.channel_activity],
        "mapped_signal_edge_counts": dict(sorted(diagnosis.mapped_signal_edge_counts.items())),
        "active_channels": [activity.__dict__.copy() for activity in diagnosis.active_channels],
        "notes": list(diagnosis.notes),
    }


if __name__ == "__main__":
    raise SystemExit(main())
