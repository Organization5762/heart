"""Helpers for recognizing, decoding, and updating FlowToy RF payloads."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

FLOWTOY_SYNC_PACKET_SIZE = 21
FLOWTOY_SCHEMA = "flowtoy.sync.v1"
FLOWTOY_HUE_OFFSET = 10
FLOWTOY_SATURATION_OFFSET = 11
FLOWTOY_BRIGHTNESS_OFFSET = 12
FLOWTOY_SPEED_OFFSET = 13
FLOWTOY_DENSITY_OFFSET = 14
FLOWTOY_FLAGS_OFFSET = 15
FLOWTOY_RESERVED_OFFSET = 16
FLOWTOY_PAGE_OFFSET = 18
FLOWTOY_MODE_OFFSET = 19
FLOWTOY_COMMAND_FLAGS_OFFSET = 20
FLOWTOY_UNKNOWN_MODE_NAME = "flowtoy-unknown"
FLOWTOY_MODE_REFERENCE_PATH = Path(__file__).with_name("flowtoy_modes.json")


@lru_cache(maxsize=1)
def _documented_modes_by_key() -> dict[tuple[int, int], dict[str, Any]]:
    """Return the documented FlowToy mode reference keyed by page and mode."""

    mode_reference = json.loads(
        FLOWTOY_MODE_REFERENCE_PATH.read_text(encoding="utf-8")
    )
    return {
        (int(entry["page"]), int(entry["mode"])): dict(entry)
        for entry in mode_reference
    }


def normalize_payload(
    payload: bytes | bytearray | memoryview | Iterable[int],
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
    payload: bytes | bytearray | memoryview | Iterable[int],
) -> bool:
    """Return ``True`` when *payload* matches the known FlowToy packet shape."""

    packet = normalize_payload(payload)
    return len(packet) >= FLOWTOY_SYNC_PACKET_SIZE


def decode_group_id(
    payload: bytes | bytearray | memoryview | Iterable[int],
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


def documented_mode_metadata(
    page: int | None,
    mode: int | None,
) -> Mapping[str, Any] | None:
    """Return the documented reference entry for a FlowToy page and mode."""

    if page is None or mode is None:
        return None
    return _documented_modes_by_key().get((int(page), int(mode)))


def decode_sync_packet(
    payload: bytes | bytearray | memoryview | Iterable[int],
) -> dict[str, Any]:
    """Decode a FlowToy sync packet into a structured mapping."""

    packet = normalize_payload(payload)[:FLOWTOY_SYNC_PACKET_SIZE]
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
            "hue": packet[FLOWTOY_HUE_OFFSET],
            "saturation": packet[FLOWTOY_SATURATION_OFFSET],
            "brightness": packet[FLOWTOY_BRIGHTNESS_OFFSET],
            "speed": packet[FLOWTOY_SPEED_OFFSET],
            "density": packet[FLOWTOY_DENSITY_OFFSET],
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
        "mode_documentation": documented_mode_metadata(page, mode),
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


def update_sync_packet_brightness(
    payload: bytes | bytearray | memoryview | Iterable[int],
    *,
    brightness: int,
) -> bytes:
    """Return *payload* with the FlowToy sync-packet brightness byte updated."""

    if not 0 <= int(brightness) <= 0xFF:
        raise ValueError("Brightness must fit in one byte")

    packet = bytearray(normalize_payload(payload))
    if not looks_like_sync_packet(packet):
        raise ValueError("Payload does not match the known FlowToy sync packet shape")
    packet[FLOWTOY_BRIGHTNESS_OFFSET] = int(brightness)
    return bytes(packet)


def decode_if_matching(
    payload: bytes | bytearray | memoryview | Iterable[int],
) -> Mapping[str, Any] | None:
    """Decode *payload* when it matches the FlowToy packet schema."""

    if not looks_like_sync_packet(payload):
        return None
    return decode_sync_packet(payload)
