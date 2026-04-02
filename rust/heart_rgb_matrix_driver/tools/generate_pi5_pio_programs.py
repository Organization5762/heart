from __future__ import annotations

import argparse
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import adafruit_pioasm

LOGGER = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parents[3]
PIO_DIR = ROOT_DIR / "rust" / "heart_rgb_matrix_driver" / "pio"
RUST_OUTPUT_PATH = (
    ROOT_DIR
    / "rust"
    / "heart_rgb_matrix_driver"
    / "src"
    / "runtime"
    / "pi5_pio_programs_generated.rs"
)
RUSTFMT_BINARY = "rustfmt"


@dataclass(frozen=True)
class ProgramSpec:
    name: str
    source_path: Path
    const_prefix: str
    delay_patch_indices: tuple[int, ...]
    out_pin_base: int
    out_pin_count: int
    out_shift_right: bool
    auto_pull: bool
    pull_threshold: int


PROGRAM_SPECS = (
    ProgramSpec(
        name="pi5_simple_hub75",
        source_path=PIO_DIR / "pi5_simple_hub75.pio",
        const_prefix="HEART_PI5_PIO_SIMPLE_HUB75",
        delay_patch_indices=(3, 4),
        out_pin_base=0,
        out_pin_count=28,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=32,
    ),
    ProgramSpec(
        name="piomatter_row_repeat_engine_parity",
        source_path=PIO_DIR / "piomatter_row_repeat_engine_parity.pio",
        const_prefix="HEART_PIOMATTER_ROW_REPEAT_ENGINE_PARITY",
        delay_patch_indices=(),
        out_pin_base=0,
        out_pin_count=28,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=32,
    ),
    ProgramSpec(
        name="piomatter_row_compact_engine_parity",
        source_path=PIO_DIR / "piomatter_row_compact_engine_parity.pio",
        const_prefix="HEART_PIOMATTER_ROW_COMPACT_ENGINE_PARITY",
        delay_patch_indices=(),
        out_pin_base=0,
        out_pin_count=28,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=32,
    ),
    ProgramSpec(
        name="piomatter_row_compact_tight_engine_parity",
        source_path=PIO_DIR / "piomatter_row_compact_tight_engine_parity.pio",
        const_prefix="HEART_PIOMATTER_ROW_COMPACT_TIGHT_ENGINE_PARITY",
        delay_patch_indices=(),
        out_pin_base=0,
        out_pin_count=28,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=32,
    ),
    ProgramSpec(
        name="piomatter_row_counted_engine_parity",
        source_path=PIO_DIR / "piomatter_row_counted_engine_parity.pio",
        const_prefix="HEART_PIOMATTER_ROW_COUNTED_ENGINE_PARITY",
        delay_patch_indices=(),
        out_pin_base=0,
        out_pin_count=28,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=32,
    ),
    ProgramSpec(
        name="piomatter_row_hybrid_engine_parity",
        source_path=PIO_DIR / "piomatter_row_hybrid_engine_parity.pio",
        const_prefix="HEART_PIOMATTER_ROW_HYBRID_ENGINE_PARITY",
        delay_patch_indices=(),
        out_pin_base=0,
        out_pin_count=28,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=32,
    ),
    ProgramSpec(
        name="piomatter_row_split_engine_parity",
        source_path=PIO_DIR / "piomatter_row_split_engine_parity.pio",
        const_prefix="HEART_PIOMATTER_ROW_SPLIT_ENGINE_PARITY",
        delay_patch_indices=(),
        out_pin_base=0,
        out_pin_count=28,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=32,
    ),
    ProgramSpec(
        name="piomatter_row_runs_engine_parity",
        source_path=PIO_DIR / "piomatter_row_runs_engine_parity.pio",
        const_prefix="HEART_PIOMATTER_ROW_RUNS_ENGINE_PARITY",
        delay_patch_indices=(),
        out_pin_base=0,
        out_pin_count=28,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=32,
    ),
    ProgramSpec(
        name="piomatter_row_window_engine_parity",
        source_path=PIO_DIR / "piomatter_row_window_engine_parity.pio",
        const_prefix="HEART_PIOMATTER_ROW_WINDOW_ENGINE_PARITY",
        delay_patch_indices=(),
        out_pin_base=0,
        out_pin_count=28,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=32,
    ),
    ProgramSpec(
        name="piomatter_symbol_command_parity",
        source_path=PIO_DIR / "piomatter_symbol_command_parity.pio",
        const_prefix="HEART_PIOMATTER_SYMBOL_COMMAND_PARITY",
        delay_patch_indices=(),
        out_pin_base=0,
        out_pin_count=13,
        out_shift_right=True,
        auto_pull=True,
        pull_threshold=30,
    ),
    ProgramSpec(
        name="pi5_resident_parser",
        source_path=PIO_DIR / "pi5_resident_parser.pio",
        const_prefix="HEART_PI5_PIO_RESIDENT_PARSER",
        delay_patch_indices=(2, 18, 19),
        out_pin_base=5,
        out_pin_count=23,
        out_shift_right=False,
        auto_pull=True,
        pull_threshold=23,
    ),
)


@dataclass(frozen=True)
class AssembledProgram:
    spec: ProgramSpec
    instructions: tuple[int, ...]
    wrap_target: int
    wrap: int
    sideset_pin_count: int
    sideset_optional: bool


def assemble_program(spec: ProgramSpec) -> AssembledProgram:
    program = adafruit_pioasm.Program.from_file(str(spec.source_path))
    wrap_target = int(program.pio_kwargs.get("wrap_target", 0))
    wrap = int(program.pio_kwargs["wrap"])
    sideset_pin_count = int(program.pio_kwargs.get("sideset_pin_count", 0))
    sideset_optional = bool(program.pio_kwargs.get("sideset_enable", False))
    instructions = tuple(int(word) for word in program.assembled)
    return AssembledProgram(
        spec=spec,
        instructions=instructions,
        wrap_target=wrap_target,
        wrap=wrap,
        sideset_pin_count=sideset_pin_count,
        sideset_optional=sideset_optional,
    )


def format_instruction_array(words: tuple[int, ...], suffix: str) -> str:
    return ",\n".join(f"    0x{word:04x}{suffix}" for word in words)


def render_rust_module(programs: tuple[AssembledProgram, ...]) -> str:
    lines = [
        "// Auto-generated by rust/heart_rgb_matrix_driver/tools/generate_pi5_pio_programs.py.",
        "#![allow(dead_code)]",
        "",
    ]
    for program in programs:
        prefix = program.spec.const_prefix.removeprefix("HEART_")
        lines.extend(
            [
                f"pub(crate) const {prefix}_PROGRAM_LENGTH: usize = {len(program.instructions)};",
                f"pub(crate) const {prefix}_WRAP_TARGET: u8 = {program.wrap_target};",
                f"pub(crate) const {prefix}_WRAP: u8 = {program.wrap};",
                f"pub(crate) const {prefix}_SIDESET_PIN_COUNT: u8 = {program.sideset_pin_count};",
                f"pub(crate) const {prefix}_SIDESET_OPTIONAL: bool = {str(program.sideset_optional).lower()};",
                f"pub(crate) const {prefix}_SIDESET_TOTAL_BITS: u8 = {program.sideset_pin_count + int(program.sideset_optional)};",
                f"pub(crate) const {prefix}_OUT_PIN_BASE: u8 = {program.spec.out_pin_base};",
                f"pub(crate) const {prefix}_OUT_PIN_COUNT: u8 = {program.spec.out_pin_count};",
                f"pub(crate) const {prefix}_OUT_SHIFT_RIGHT: bool = {str(program.spec.out_shift_right).lower()};",
                f"pub(crate) const {prefix}_AUTO_PULL: bool = {str(program.spec.auto_pull).lower()};",
                f"pub(crate) const {prefix}_PULL_THRESHOLD: u8 = {program.spec.pull_threshold};",
                f"pub(crate) const {prefix}_DELAY_PATCH_INDICES: [usize; {len(program.spec.delay_patch_indices)}] = {list(program.spec.delay_patch_indices)};",
                f"pub(crate) const {prefix}_BASE_PROGRAM: [u16; {len(program.instructions)}] = [",
                format_instruction_array(program.instructions, ""),
                "];",
                "",
            ]
        )
    content = "\n".join(lines)
    try:
        result = subprocess.run(
            [RUSTFMT_BINARY, "--emit", "stdout"],
            check=True,
            input=content,
            text=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return content
    return result.stdout


def write_text_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble Pi 5 PIO .pio sources into checked-in C and Rust outputs."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the generated outputs differ from the checked-in files.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    programs = tuple(assemble_program(spec) for spec in PROGRAM_SPECS)
    rust_module = render_rust_module(programs)

    changed_paths = []
    for path, content in ((RUST_OUTPUT_PATH, rust_module),):
        if write_text_if_changed(path, content):
            changed_paths.append(path)

    if args.check:
        if changed_paths:
            for path in changed_paths:
                LOGGER.error("Generated output was stale: %s", path)
            return 1
        LOGGER.info("Pi 5 PIO generated outputs are up to date.")
        return 0

    if changed_paths:
        for path in changed_paths:
            LOGGER.info("Wrote %s", path)
    else:
        LOGGER.info("Pi 5 PIO generated outputs already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
