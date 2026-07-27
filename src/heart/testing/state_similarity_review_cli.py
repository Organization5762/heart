from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import final

from heart.testing.state_similarity_review import (
    DEFAULT_REVIEW_OUTPUT, DEFAULT_TRANSITION_FRAMES,
    generate_state_similarity_review)
from heart.testing.system_contract import write_system_contract_review

DEFAULT_SCENARIO_DIRECTORY = Path("tests/state_similarity/scenarios")
_SLUG_CHARACTERS = re.compile(r"[^a-z0-9]+")


@final
@dataclass(frozen=True)
class ReviewCliArguments:
    paths: tuple[Path, ...]
    output: Path
    transition_frames: int
    contract_artifacts: tuple[Path, ...]


def main(argv: Sequence[str] | None = None) -> None:
    """Generate static state-similarity review pages."""

    arguments = parse_args(argv)
    result = generate_state_similarity_review(
        arguments.paths,
        output_dir=arguments.output,
        transition_frames=arguments.transition_frames,
    )
    for artifact_path in arguments.contract_artifacts:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        write_system_contract_review(
            artifact,
            arguments.output / f"{_slug(artifact_path.stem)}-system-contract.html",
        )
    print(result.index_path)


def parse_args(argv: Sequence[str] | None = None) -> ReviewCliArguments:
    parser = argparse.ArgumentParser(
        prog="heart-state-review",
        description="Replay state-similarity JSON scenarios into static HTML.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Scenario JSON files or directories containing scenario JSON files.",
    )
    parser.add_argument(
        "--scenario-dir",
        action="append",
        default=[],
        type=Path,
        help="Additional directory containing scenario JSON files.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_REVIEW_OUTPUT,
        type=Path,
        help=f"Output directory (default: {DEFAULT_REVIEW_OUTPUT}).",
    )
    parser.add_argument(
        "--transition-frames",
        default=DEFAULT_TRANSITION_FRAMES,
        type=_non_negative_integer,
        help=(
            "Maximum isolated frames sampled for each animated scene transition "
            f"(default: {DEFAULT_TRANSITION_FRAMES})."
        ),
    )
    parser.add_argument(
        "--contract-artifact",
        action="append",
        default=[],
        type=Path,
        help=(
            "Machine-readable system qualification artifact to render as an "
            "additional contract review page."
        ),
    )
    namespace = parser.parse_args(argv)
    paths = tuple(namespace.paths) + tuple(namespace.scenario_dir)
    if not paths:
        paths = (DEFAULT_SCENARIO_DIRECTORY,)
    return ReviewCliArguments(
        paths=paths,
        output=namespace.output,
        transition_frames=namespace.transition_frames,
        contract_artifacts=tuple(namespace.contract_artifact),
    )


def _non_negative_integer(raw_value: str) -> int:
    value = int(raw_value)
    if value < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return value


def _slug(stem: str) -> str:
    return _SLUG_CHARACTERS.sub("-", stem.lower()).strip("-") or "artifact"
