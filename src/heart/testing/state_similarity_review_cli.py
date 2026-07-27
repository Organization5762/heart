from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import final

from heart.testing.state_similarity_review import (
    DEFAULT_REVIEW_OUTPUT,
    DEFAULT_TRANSITION_FRAMES,
    generate_state_similarity_review,
)
DEFAULT_SCENARIO_DIRECTORY = Path("tests/state_similarity/scenarios")


@final
@dataclass(frozen=True)
class ReviewCliArguments:
    paths: tuple[Path, ...]
    output: Path
    transition_frames: int


def main(argv: Sequence[str] | None = None) -> None:
    """Generate static state-similarity review pages."""

    arguments = parse_args(argv)
    result = generate_state_similarity_review(
        arguments.paths,
        output_dir=arguments.output,
        transition_frames=arguments.transition_frames,
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
    namespace = parser.parse_args(argv)
    paths = tuple(namespace.paths) + tuple(namespace.scenario_dir)
    if not paths:
        paths = (DEFAULT_SCENARIO_DIRECTORY,)
    return ReviewCliArguments(
        paths=paths,
        output=namespace.output,
        transition_frames=namespace.transition_frames,
    )


def _non_negative_integer(raw_value: str) -> int:
    value = int(raw_value)
    if value < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return value
