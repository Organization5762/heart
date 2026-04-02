from __future__ import annotations

import argparse
import io
import logging
from contextlib import redirect_stdout
from pathlib import Path

import adafruit_pioasm

LOGGER = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_PATH = (
    ROOT_DIR
    / "docs"
    / "research"
    / "generated"
    / "piomatter_override"
    / "protomatter.pio.h"
)
DEFAULT_SYMBOL_PREFIX = "protomatter"


def default_source_path() -> Path:
    candidates = (
        ROOT_DIR / "rust" / "heart_rgb_matrix_driver" / "pio" / "piomatter_protomatter_parity.pio",
        ROOT_DIR / "rust" / "heart_rust" / "pio" / "piomatter_protomatter_parity.pio",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble the Piomatter parity .pio source into a Piomatter-compatible header."
    )
    parser.add_argument("--source", type=Path, default=default_source_path())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--symbol-prefix",
        type=str,
        default=DEFAULT_SYMBOL_PREFIX,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the generated header differs from the checked-in output.",
    )
    return parser.parse_args()


def render_header(source_path: Path, symbol_prefix: str) -> str:
    program = adafruit_pioasm.Program.from_file(
        str(source_path),
        build_debuginfo=True,
    )
    c_program = io.StringIO()
    with redirect_stdout(c_program):
        program.print_c_program(symbol_prefix)
    return "\n".join(
        [
            "#pragma once",
            "",
            c_program.getvalue().rstrip().replace("True", "true"),
            "",
        ]
    )


def write_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    content = render_header(args.source, args.symbol_prefix)
    changed = write_if_changed(args.output, content)
    if args.check:
        if changed:
            LOGGER.error("Generated Piomatter parity header was stale: %s", args.output)
            return 1
        LOGGER.info("Piomatter parity header is up to date.")
        return 0
    if changed:
        LOGGER.info("Wrote %s", args.output)
    else:
        LOGGER.info("Piomatter parity header already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
