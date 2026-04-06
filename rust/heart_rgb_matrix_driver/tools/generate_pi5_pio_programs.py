from __future__ import annotations

from pathlib import Path

import adafruit_pioasm

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

PROGRAMS = (
    {
        "name": "PI5_PIO_RAW_BYTE_PULL",
        "path": PIO_DIR / "pi5_raw_byte_pull.pio",
        "delay_patch_indices": (),
        "out_pin_base": 0,
        "out_pin_count": 28,
        "out_shift_right": False,
        "auto_pull": False,
        "pull_threshold": 28,
    },
    {
        "name": "PI5_PIO_ROUND_ROBIN_OUT",
        "path": PIO_DIR / "round_robin.pio",
        "delay_patch_indices": (),
        "out_pin_base": 0,
        "out_pin_count": 31,
        "out_shift_right": False,
        "auto_pull": True,
        "pull_threshold": 32,
    },
)


def format_bool(value: bool) -> str:
    return "true" if value else "false"


def main() -> None:
    lines = ["#![allow(dead_code)]", ""]
    for spec in PROGRAMS:
        program = adafruit_pioasm.Program(spec["path"].read_text(encoding="utf-8"))
        assembled = list(program.assembled)
        instructions = ", ".join(f"0x{opcode:04x}" for opcode in assembled)
        delay_patch_indices = ", ".join(str(index) for index in spec["delay_patch_indices"])
        prefix = spec["name"]
        lines.extend(
            [
                f"pub(crate) const {prefix}_PROGRAM_LENGTH: usize = {len(assembled)};",
                f"pub(crate) const {prefix}_WRAP_TARGET: u8 = {program.pio_kwargs['wrap_target']};",
                f"pub(crate) const {prefix}_WRAP: u8 = {program.pio_kwargs['wrap']};",
                f"pub(crate) const {prefix}_SIDESET_PIN_COUNT: u8 = {program.pio_kwargs.get('sideset_pin_count', 0)};",
                f"pub(crate) const {prefix}_SIDESET_OPTIONAL: bool = {format_bool(program.pio_kwargs.get('sideset_enable', False))};",
                f"pub(crate) const {prefix}_OUT_PIN_BASE: u8 = {spec['out_pin_base']};",
                f"pub(crate) const {prefix}_OUT_PIN_COUNT: u8 = {spec['out_pin_count']};",
                f"pub(crate) const {prefix}_OUT_SHIFT_RIGHT: bool = {format_bool(spec['out_shift_right'])};",
                f"pub(crate) const {prefix}_AUTO_PULL: bool = {format_bool(spec['auto_pull'])};",
                f"pub(crate) const {prefix}_PULL_THRESHOLD: u8 = {spec['pull_threshold']};",
                f"pub(crate) const {prefix}_DELAY_PATCH_INDICES: [usize; {len(spec['delay_patch_indices'])}] = [{delay_patch_indices}];",
                f"pub(crate) const {prefix}_BASE_PROGRAM: [u16; {len(assembled)}] = [{instructions}];",
                "",
            ]
        )
    RUST_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
