"""Helpers for recognizing and decoding FlowToy RF payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

FLOWTOY_SYNC_PACKET_SIZE = 21
FLOWTOY_SCHEMA = "flowtoy.sync.v1"
FLOWTOY_FLAGS_OFFSET = 15
FLOWTOY_RESERVED_OFFSET = 16
FLOWTOY_PAGE_OFFSET = 18
FLOWTOY_MODE_OFFSET = 19
FLOWTOY_COMMAND_FLAGS_OFFSET = 20
FLOWTOY_UNKNOWN_MODE_NAME = "flowtoy-unknown"


def normalize_payload(
    payload: bytes | bytearray | memoryview | Sequence[int],
) -> bytes:
    """Normalize a payload into raw bytes."""

    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload)

    normalized: list[int] = []
    for value in payload:
        if not isinstance(value, int):
            raise TypeError("FlowToy payload sequences must contain integers")
        normalized.append(int(value) & 0xFF)
    return bytes(normalized)


def looks_like_sync_packet(
    payload: bytes | bytearray | memoryview | Sequence[int],
) -> bool:
    """Return ``True`` when *payload* matches the known FlowToy packet shape."""

    packet = normalize_payload(payload)
    return len(packet) == FLOWTOY_SYNC_PACKET_SIZE


def decode_group_id(
    payload: bytes | bytearray | memoryview | Sequence[int],
) -> int:
    """Decode the byte-swapped group identifier from *payload*."""

    packet = normalize_payload(payload)
    raw_group_id = int.from_bytes(packet[0:2], byteorder="little", signed=False)
    return ((raw_group_id & 0xFF) << 8) | ((raw_group_id >> 8) & 0xFF)


def mode_name_from_values(page: int | None, mode: int | None) -> str:
    """Build a stable mode label from FlowToy page and mode values."""

    if page is None or mode is None:
        return FLOWTOY_UNKNOWN_MODE_NAME
    return f"flowtoy-page-{int(page)}-mode-{int(mode)}"


def mode_name_from_decoded(decoded: Mapping[str, Any] | None) -> str:
    """Return a mode label derived from a decoded FlowToy payload."""

    if decoded is None:
        return FLOWTOY_UNKNOWN_MODE_NAME
    page = decoded.get("page")
    mode = decoded.get("mode")
    if not isinstance(page, int) or not isinstance(mode, int):
        return FLOWTOY_UNKNOWN_MODE_NAME
    return mode_name_from_values(page, mode)


def decode_sync_packet(
    payload: bytes | bytearray | memoryview | Sequence[int],
) -> dict[str, Any]:
    """Decode a FlowToy sync packet into a structured mapping."""

    packet = normalize_payload(payload)
    if not looks_like_sync_packet(packet):
        raise ValueError("Payload does not match the known FlowToy sync packet shape")

    radio_flags = packet[FLOWTOY_FLAGS_OFFSET]
    command_flags = packet[FLOWTOY_COMMAND_FLAGS_OFFSET]
    page = packet[FLOWTOY_PAGE_OFFSET]
    mode = packet[FLOWTOY_MODE_OFFSET]

    return {
        "schema": FLOWTOY_SCHEMA,
        "group_id": decode_group_id(packet),
        "padding": int.from_bytes(packet[2:6], byteorder="little", signed=False),
        "lfo": [int(value) for value in packet[6:10]],
        "global": {
            "hue": packet[10],
            "saturation": packet[11],
            "brightness": packet[12],
            "speed": packet[13],
            "density": packet[14],
        },
        "active_flags": {
            "lfo": bool(radio_flags & (1 << 0)),
            "hue": bool(radio_flags & (1 << 1)),
            "saturation": bool(radio_flags & (1 << 2)),
            "brightness": bool(radio_flags & (1 << 3)),
            "speed": bool(radio_flags & (1 << 4)),
            "density": bool(radio_flags & (1 << 5)),
        },
        "reserved": [int(packet[FLOWTOY_RESERVED_OFFSET]), int(packet[FLOWTOY_RESERVED_OFFSET + 1])],
        "page": page,
        "mode": mode,
        "mode_name": mode_name_from_values(page, mode),
        "command_flags": {
            "adjust_active": bool(command_flags & (1 << 0)),
            "wakeup": bool(command_flags & (1 << 1)),
            "poweroff": bool(command_flags & (1 << 2)),
            "force_reload": bool(command_flags & (1 << 3)),
            "save": bool(command_flags & (1 << 4)),
            "delete": bool(command_flags & (1 << 5)),
            "alternate": bool(command_flags & (1 << 6)),
        },
    }


def decode_if_matching(
    payload: bytes | bytearray | memoryview | Sequence[int],
) -> Mapping[str, Any] | None:
    """Decode *payload* when it matches the FlowToy packet schema."""

    if not looks_like_sync_packet(payload):
        return None
    return decode_sync_packet(payload)
