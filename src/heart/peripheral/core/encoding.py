from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum, StrEnum
from typing import Any, Mapping, Sequence, cast
from uuid import UUID

from google.protobuf.message import Message

from heart.peripheral.core import Input
from heart.peripheral.core.protobuf_registry import protobuf_registry
from heart.peripheral.core.protobuf_types import (INPUT_EVENT_TYPE,
                                                  PeripheralPayloadType)
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


class PeripheralPayloadEncodingError(ValueError):
    """Raised when a peripheral payload cannot be encoded."""


def _get_message_class(
    payload_type: str | PeripheralPayloadType,
) -> type[Message]:
    message_class = protobuf_registry.get_message_class(payload_type)
    if message_class is None:
        normalized = _normalize_payload_type(payload_type)
        logger.error(
            "Protobuf payload type '%s' is not registered for encoding.",
            normalized,
        )
        raise PeripheralPayloadEncodingError(
            f"Unknown protobuf payload type: {normalized}"
        )
    return message_class


def _encode_input_payload(payload: Input) -> PeripheralPayload:
    message_class = _get_message_class(INPUT_EVENT_TYPE)
    normalized = _normalize_payload(payload.data)
    data_json = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    event = message_class(
        event_type=payload.event_type,
        timestamp=payload.timestamp.isoformat(),
        data_json=data_json,
    )
    return PeripheralPayload(
        payload=event.SerializeToString(),
        encoding=PeripheralPayloadEncoding.PROTOBUF,
        payload_type=event.DESCRIPTOR.full_name,
    )


def _decode_input_event(message: Message) -> Input:
    event = cast(Any, message)
    try:
        data = json.loads(event.data_json.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.exception("Failed to decode InputEvent payload data.")
        raise PeripheralPayloadDecodingError(
            "Failed to decode InputEvent payload data."
        ) from exc
    try:
        timestamp = datetime.fromisoformat(event.timestamp)
    except ValueError as exc:
        logger.exception("Failed to decode InputEvent timestamp.")
        raise PeripheralPayloadDecodingError(
            "Failed to decode InputEvent timestamp."
        ) from exc
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return Input(
        event_type=event.event_type,
        data=data,
        timestamp=timestamp,
    )


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
    if isinstance(payload, Input):
        return _encode_input_payload(payload)

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
    payload_type: str | PeripheralPayloadType = "",
) -> object:
    normalized_payload_type = _normalize_payload_type(payload_type)
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
        if not normalized_payload_type:
            raise PeripheralPayloadDecodingError(
                "Protobuf payloads require a payload_type."
            )
        message_class = protobuf_registry.get_message_class(normalized_payload_type)
        if message_class is None:
            raise PeripheralPayloadDecodingError(
                f"Unknown protobuf payload type: {normalized_payload_type}"
            )
        message = message_class()
        try:
            message.ParseFromString(payload)
        except Exception as exc:
            logger.exception(
                "Failed to decode protobuf payload for type %s.",
                normalized_payload_type,
            )
            raise PeripheralPayloadDecodingError(
                f"Failed to decode protobuf payload for type {normalized_payload_type}."
            ) from exc
        if normalized_payload_type == INPUT_EVENT_TYPE:
            return _decode_input_event(message)
        return message

    raise PeripheralPayloadDecodingError(
        f"Unsupported peripheral payload encoding: {encoding}"
    )


def _normalize_payload_type(payload_type: str | PeripheralPayloadType) -> str:
    if isinstance(payload_type, PeripheralPayloadType):
        return payload_type.value
    return payload_type
