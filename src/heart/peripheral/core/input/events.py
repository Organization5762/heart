from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any

from manyfold.architecture import PubSubTopic

HEART_INPUT_PUBSUB = "heart"
INPUT_EVENT_TOPIC = "heart.input"
FRAME_TICK_TOPIC = "heart.frame_tick"


@dataclass(frozen=True, slots=True)
class InputEvent:
    event_type: str
    source_id: str
    stream_name: str
    stage: str
    payload_json: str
    timestamp_monotonic: float

    @classmethod
    def from_payload(
        cls,
        *,
        event_type: str,
        source_id: str,
        stream_name: str,
        stage: str,
        payload: Any,
        timestamp_monotonic: float,
    ) -> "InputEvent":
        return cls(
            event_type=event_type,
            source_id=source_id,
            stream_name=stream_name,
            stage=stage,
            payload_json=json.dumps(
                _jsonable(payload),
                sort_keys=True,
                separators=(",", ":"),
            ),
            timestamp_monotonic=timestamp_monotonic,
        )


def input_event_topic() -> Any:
    return PubSubTopic(
        INPUT_EVENT_TOPIC,
        schema=InputEvent,
        pubsub=HEART_INPUT_PUBSUB,
    )


def frame_tick_topic(schema: type[Any]) -> Any:
    return PubSubTopic(
        FRAME_TICK_TOPIC,
        schema=schema,
        pubsub=HEART_INPUT_PUBSUB,
    )


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(_jsonable(key)): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if isinstance(value, frozenset | set):
        return [_jsonable(item) for item in sorted(value, key=str)]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return repr(value)
