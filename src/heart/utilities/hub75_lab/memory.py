"""RP1 shared-SRAM validation for HUB75 experiment plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

RP1_PAYLOAD_OFFSET = 0x8000
RP1_FIRMWARE_MAILBOX_OFFSET = 0xFF00
RP1_SRAM_WINDOW_END = 0x10000
DEFAULT_REQUIRED_ALIGNMENT = 4


def validate_sram_buffer(
    *,
    payload_size: int,
    source_offset: int,
    source_size: int,
    required_alignment: int = DEFAULT_REQUIRED_ALIGNMENT,
) -> SramBufferLayout:
    """Validate one source buffer against the documented RP1 SRAM boundaries."""

    if payload_size <= 0:
        raise ValueError(f"payload_size must be positive, got {payload_size}")
    if source_size <= 0:
        raise ValueError(f"source_size must be positive, got {source_size}")
    if required_alignment <= 0 or required_alignment & (required_alignment - 1):
        raise ValueError(
            "required_alignment must be a positive power of two, "
            f"got {required_alignment}"
        )
    if source_offset % required_alignment:
        raise ValueError(
            f"source_offset 0x{source_offset:x} is not aligned to "
            f"0x{required_alignment:x}"
        )
    if source_offset < 0 or source_offset >= RP1_SRAM_WINDOW_END:
        raise ValueError(
            f"source_offset must be inside [0x0,0x{RP1_SRAM_WINDOW_END:x}), "
            f"got 0x{source_offset:x}"
        )
    if source_size > RP1_SRAM_WINDOW_END:
        raise ValueError(
            f"source_size 0x{source_size:x} exceeds the 64 KiB SRAM window"
        )

    payload_end = RP1_PAYLOAD_OFFSET + payload_size
    minimum_source_offset = _align_up(payload_end, required_alignment)
    source_end = source_offset + source_size
    if source_end < source_offset or source_end > RP1_SRAM_WINDOW_END:
        raise ValueError(
            f"source range arithmetic escaped the SRAM window: "
            f"[0x{source_offset:x},0x{source_end:x})"
        )

    if payload_end > RP1_FIRMWARE_MAILBOX_OFFSET:
        raise ValueError(
            f"payload ends at 0x{payload_end:x}, inside or beyond the reserved "
            f"firmware mailbox at 0x{RP1_FIRMWARE_MAILBOX_OFFSET:x}"
        )
    if source_offset < minimum_source_offset:
        raise ValueError(
            f"source starts at 0x{source_offset:x}, before the aligned payload "
            f"end 0x{minimum_source_offset:x}"
        )
    if source_end > RP1_FIRMWARE_MAILBOX_OFFSET:
        raise ValueError(
            f"source ends at 0x{source_end:x}, beyond the safe data window ending "
            f"at 0x{RP1_FIRMWARE_MAILBOX_OFFSET:x}"
        )

    return SramBufferLayout(
        payload_size=payload_size,
        payload_end=payload_end,
        source_offset=source_offset,
        source_size=source_size,
        source_end=source_end,
        required_alignment=required_alignment,
    )


@final
@dataclass(frozen=True)
class SramBufferLayout:
    """One source buffer proven not to overlap a payload or firmware mailbox."""

    payload_size: int
    payload_end: int
    source_offset: int
    source_size: int
    source_end: int
    required_alignment: int


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)
