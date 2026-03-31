"""Helpers for recognizing and decoding FlowToy RF payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

FLOWTOY_SYNC_PACKET_SIZE = 21
FLOWTOY_GROUP_ID_MAX = 1024
FLOWTOY_RESERVED_OFFSET = 16
FLOWTOY_FLAGS_OFFSET = 15
FLOWTOY_COMMAND_FLAGS_OFFSET = 20


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
    if len(packet) != FLOWTOY_SYNC_PACKET_SIZE:
        return False

    radio_flags = packet[FLOWTOY_FLAGS_OFFSET]
    command_flags = packet[FLOWTOY_COMMAND_FLAGS_OFFSET]
    if radio_flags & 0b1100_0000:
        return False
    if command_flags & 0b1000_0000:
        return False

    if any(packet[index] != 0 for index in range(FLOWTOY_RESERVED_OFFSET, FLOWTOY_RESERVED_OFFSET + 2)):
        return False

    group_id = decode_group_id(packet)
    return 0 < group_id <= FLOWTOY_GROUP_ID_MAX


def decode_group_id(
    payload: bytes | bytearray | memoryview | Sequence[int],
) -> int:
    """Decode the byte-swapped group identifier from *payload*."""

    packet = normalize_payload(payload)
    raw_group_id = int.from_bytes(packet[0:2], byteorder="little", signed=False)
    return ((raw_group_id & 0xFF) << 8) | ((raw_group_id >> 8) & 0xFF)


def decode_sync_packet(
    payload: bytes | bytearray | memoryview | Sequence[int],
) -> dict[str, Any]:
    """Decode a FlowToy sync packet into a structured mapping."""

    packet = normalize_payload(payload)
    if not looks_like_sync_packet(packet):
        raise ValueError("Payload does not match the known FlowToy sync packet shape")

    radio_flags = packet[FLOWTOY_FLAGS_OFFSET]
    command_flags = packet[FLOWTOY_COMMAND_FLAGS_OFFSET]

    return {
        "schema": "flowtoy.sync.v1",
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
        "page": packet[18],
        "mode": packet[19],
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
