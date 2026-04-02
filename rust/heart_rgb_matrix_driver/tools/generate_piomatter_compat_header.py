from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import adafruit_pioasm

LOGGER = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parents[3]
PIO_DIR = ROOT_DIR / "rust" / "heart_rgb_matrix_driver" / "pio"
DEFAULT_OUTPUT_PATH = (
    ROOT_DIR
    / "docs"
    / "research"
    / "generated"
    / "piomatter_override"
    / "protomatter.pio.h"
)


@dataclass(frozen=True)
class CompatProgram:
    source_path: Path
    symbol_prefix: str


DEFAULT_PROGRAM = CompatProgram(
    source_path=PIO_DIR / "pi5_simple_hub75.pio",
    symbol_prefix="protomatter",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble a .pio file into a Piomatter-compatible .pio.h header."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_PROGRAM.source_path,
        help="Path to the .pio source to assemble.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Header path to write.",
    )
    parser.add_argument(
        "--symbol-prefix",
        type=str,
        default=DEFAULT_PROGRAM.symbol_prefix,
        help="Prefix for the generated instruction and wrap symbols.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the checked-in header differs from regenerated output.",
    )
    return parser.parse_args()


def assemble_program(source_path: Path) -> adafruit_pioasm.Program:
    return adafruit_pioasm.Program.from_file(str(source_path))


def render_header(
    program: adafruit_pioasm.Program, symbol_prefix: str, source_path: Path
) -> str:
    instructions = tuple(int(word) for word in program.assembled)
    wrap_target = int(program.pio_kwargs.get("wrap_target", 0))
    wrap = int(program.pio_kwargs["wrap"])
    instruction_lines = ",\n".join(f"    0x{word:04x}" for word in instructions)
    return "\n".join(
        [
            f"/* Auto-generated from {source_path.name} for Piomatter compatibility. */",
            "#pragma once",
            "#include <stdint.h>",
            "",
            f"static const uint16_t {symbol_prefix}[] = {{",
            instruction_lines,
            "};",
            "",
            f"static const uint {symbol_prefix}_wrap_target = {wrap_target};",
            f"static const uint {symbol_prefix}_wrap = {wrap};",
            "",
        ]
    )


def write_text_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    program = assemble_program(args.source)
    content = render_header(program, args.symbol_prefix, args.source)
    changed = write_text_if_changed(args.output, content)

    if args.check:
        if changed:
            LOGGER.error("Generated Piomatter compatibility header was stale: %s", args.output)
            return 1
        LOGGER.info("Piomatter compatibility header is up to date.")
        return 0

    if changed:
        LOGGER.info("Wrote %s", args.output)
    else:
        LOGGER.info("Piomatter compatibility header already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
