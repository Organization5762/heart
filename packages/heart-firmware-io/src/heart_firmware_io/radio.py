"""Helpers for receive-only radio bridge payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from heart_firmware_io import constants, flowtoy

END_OF_MESSAGE_DELIMETER = "\n"
ENCODING = "utf-8"
FLOWTOY_PROTOCOL = "flowtoy"
FLOWTOY_CHANNEL = 2
FLOWTOY_BITRATE_KBPS = 250
FLOWTOY_MODULATION = "nrf24-shockburst"
FLOWTOY_ADDRESS_WIDTH_BYTES = 3
FLOWTOY_CRC_BITS = 16
FLOWTOY_ADDRESS = (0x01, 0x07, 0xF1)


def normalize_radio_payload(
    payload: bytes | bytearray | memoryview | Sequence[int],
) -> list[int]:
    """Convert *payload* into a JSON-friendly list of unsigned bytes."""

    if isinstance(payload, (bytes, bytearray, memoryview)):
        return [int(value) & 0xFF for value in bytes(payload)]

    normalized: list[int] = []
    for value in payload:
        if not isinstance(value, int):
            raise TypeError("Radio payload sequences must contain integers")
        normalized.append(int(value) & 0xFF)
    return normalized


def flowtoy_default_metadata() -> dict[str, Any]:
    """Return the known RF parameters from the Flowtoys reference bridge."""

    return {
        "address": list(FLOWTOY_ADDRESS),
        "address_width_bytes": FLOWTOY_ADDRESS_WIDTH_BYTES,
        "crc_bits": FLOWTOY_CRC_BITS,
    }


def build_radio_packet_data(
    payload: bytes | bytearray | memoryview | Sequence[int],
    *,
    protocol: str = FLOWTOY_PROTOCOL,
    channel: int = FLOWTOY_CHANNEL,
    bitrate_kbps: int = FLOWTOY_BITRATE_KBPS,
    modulation: str = FLOWTOY_MODULATION,
    crc_ok: bool | None = None,
    frequency_hz: float | None = None,
    rssi_dbm: float | None = None,
    metadata: Mapping[str, Any] | None = None,
    decoded: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical radio packet payload sent over the USB serial bridge."""

    frame: dict[str, Any] = {
        "protocol": protocol,
        "channel": channel,
        "bitrate_kbps": bitrate_kbps,
        "modulation": modulation,
        "payload": normalize_radio_payload(payload),
    }
    if crc_ok is not None:
        frame["crc_ok"] = bool(crc_ok)
    if frequency_hz is not None:
        frame["frequency_hz"] = float(frequency_hz)
    if rssi_dbm is not None:
        frame["rssi_dbm"] = float(rssi_dbm)

    combined_metadata = flowtoy_default_metadata()
    if metadata:
        combined_metadata.update(dict(metadata))
    frame["metadata"] = combined_metadata
    if decoded:
        frame["decoded"] = dict(decoded)
    return frame


def format_radio_packet_event(
    payload: bytes | bytearray | memoryview | Sequence[int],
    **kwargs: Any,
) -> str:
    """Encode a newline-delimited radio packet event for the host serial bridge."""

    decoded = kwargs.pop("decoded", None)
    if decoded is None:
        decoded = flowtoy.decode_if_matching(payload)
    event = {
        "event_type": constants.RADIO_PACKET,
        "data": build_radio_packet_data(payload, decoded=decoded, **kwargs),
    }
    return f"{json.dumps(event)}{END_OF_MESSAGE_DELIMETER}"
