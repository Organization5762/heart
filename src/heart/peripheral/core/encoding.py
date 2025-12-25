from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, StrEnum
from typing import Mapping, Sequence
from uuid import UUID

from google.protobuf.message import Message  # type: ignore[import-untyped]


class PeripheralPayloadEncoding(StrEnum):
    JSON_UTF8 = "json_utf8"
    PROTOBUF = "protobuf"


@dataclass(frozen=True, slots=True)
class PeripheralPayload:
    payload: bytes
    encoding: PeripheralPayloadEncoding
    payload_type: str = ""


def _normalize_payload(payload: object) -> object:
    if dataclasses.is_dataclass(payload):
        return dataclasses.asdict(payload)  # type: ignore[arg-type]

    if isinstance(payload, Enum):
        return payload.value

    if isinstance(payload, UUID):
        return str(payload)

    if isinstance(payload, (datetime, date)):
        return payload.isoformat()

    if isinstance(payload, bytes):
        return payload.hex()

    if isinstance(payload, Mapping):
        return {
            str(key): _normalize_payload(value)
            for key, value in payload.items()
        }

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return [_normalize_payload(value) for value in payload]

    return payload


def encode_peripheral_payload(payload: object) -> PeripheralPayload:
    if isinstance(payload, Message):
        return PeripheralPayload(
            payload=payload.SerializeToString(),
            encoding=PeripheralPayloadEncoding.PROTOBUF,
            payload_type=payload.DESCRIPTOR.full_name,
        )

    normalized = _normalize_payload(payload)
    encoded_payload = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return PeripheralPayload(
        payload=encoded_payload,
        encoding=PeripheralPayloadEncoding.JSON_UTF8,
        payload_type="",
    )
