from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, StrEnum
from typing import Mapping, Sequence
from uuid import UUID

from google.protobuf.message import Message

from heart.peripheral.core.protobuf_registry import protobuf_registry
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PeripheralPayloadEncoding(StrEnum):
    JSON_UTF8 = "json_utf8"
    PROTOBUF = "protobuf"


@dataclass(frozen=True, slots=True)
class PeripheralPayload:
    payload: bytes
    encoding: PeripheralPayloadEncoding
    payload_type: str = ""


class PeripheralPayloadDecodingError(ValueError):
    """Raised when a peripheral payload cannot be decoded."""


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


def decode_peripheral_payload(
    payload: bytes,
    *,
    encoding: PeripheralPayloadEncoding,
    payload_type: str = "",
) -> object:
    if encoding == PeripheralPayloadEncoding.JSON_UTF8:
        try:
            decoded = payload.decode("utf-8")
            return json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.exception("Failed to decode JSON peripheral payload.")
            raise PeripheralPayloadDecodingError(
                "Failed to decode JSON peripheral payload."
            ) from exc

    if encoding == PeripheralPayloadEncoding.PROTOBUF:
        if not payload_type:
            raise PeripheralPayloadDecodingError(
                "Protobuf payloads require a payload_type."
            )
        message_class = protobuf_registry.get_message_class(payload_type)
        if message_class is None:
            raise PeripheralPayloadDecodingError(
                f"Unknown protobuf payload type: {payload_type}"
            )
        message = message_class()
        try:
            message.ParseFromString(payload)
        except Exception as exc:
            logger.exception(
                "Failed to decode protobuf payload for type %s.",
                payload_type,
            )
            raise PeripheralPayloadDecodingError(
                f"Failed to decode protobuf payload for type {payload_type}."
            ) from exc
        return message

    raise PeripheralPayloadDecodingError(
        f"Unsupported peripheral payload encoding: {encoding}"
    )
