"""Score one HUB75 logic CSV against another."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from heart.utilities.hub75_logic_score import score_hub75_capture_files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", help="baseline Saleae raw digital CSV export")
    parser.add_argument("candidate", help="candidate Saleae raw digital CSV export")
    parser.add_argument("--cols", type=int, default=64)
    args = parser.parse_args()

    baseline, candidate, score = score_hub75_capture_files(
        args.baseline,
        args.candidate,
        cols=args.cols,
    )
    payload = {
        "baseline": _summary_payload(baseline),
        "candidate": _summary_payload(candidate),
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


def _summary_payload(summary: object) -> dict[str, object]:
    summary_dict = summary.__dict__.copy()
    summary_dict["address_edges_per_lat"] = dict(
        sorted(summary_dict["address_edges_per_lat"].items())
    )
    return summary_dict


if __name__ == "__main__":
    raise SystemExit(main())
