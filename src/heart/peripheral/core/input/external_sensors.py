from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, cast

from manyfold import Graph, Subscribable
from manyfold.architecture import (PubSub, PubSubCallbackSubscription,
                                   PubSubTopic)

from heart.peripheral.core.input.debug import InputDebugStage, InputDebugTap
from heart.peripheral.core.streams import GraphRouteStream, runtime_route
from heart.peripheral.sensor import Acceleration

ACCELEROMETER_PATHS = frozenset({"x", "y", "z"})
EXTERNAL_SENSOR_STREAM_NAME = "beats.sensor.control"
EXTERNAL_SENSOR_SOURCE = "beats.sensor"
EXTERNAL_SENSOR_STATE_TOPIC = "heart.sensor.external.state"
HEART_SENSOR_PUBSUB = "heart"
EXTERNAL_ACCELEROMETER_ROUTE = runtime_route(
    "external_sensor.accelerometer",
    "HeartExternalSensorAcceleration",
)


@dataclass(frozen=True, slots=True)
class ExternalSensorUpdate:
    sensor_key: str
    peripheral_id: str
    path: str
    value: float | None


@dataclass(frozen=True, slots=True)
class ExternalSensorStateEvent:
    """Low-rate external sensor state eligible for best-effort node sharing."""

    sensor_key: str
    value: float | None
    event_id: str = ""
    origin_node_id: str = ""


def external_sensor_state_topic() -> PubSub:
    return PubSubTopic(
        EXTERNAL_SENSOR_STATE_TOPIC,
        schema=ExternalSensorStateEvent,
        pubsub=HEART_SENSOR_PUBSUB,
    )


class ExternalSensorHub:
    def __init__(self, debug_tap: InputDebugTap, *, graph: Graph | None = None) -> None:
        self._debug_tap = debug_tap
        self._graph = graph or Graph()
        self._lock = Lock()
        self._values: dict[str, float] = {}
        self._peripheral_snapshots: dict[str, dict[str, Any]] = {}
        self._accelerometer_stream: GraphRouteStream[Acceleration | None] = (
            GraphRouteStream(self._graph, EXTERNAL_ACCELEROMETER_ROUTE)
        )
        self._state_topic = external_sensor_state_topic()
        self._state_subscription: PubSubCallbackSubscription = (
            self._state_topic.subscribe(self._apply_state)
        )
        self._accelerometer_stream.emit(None)

    def set_value(self, sensor_key: str, value: float) -> None:
        _split_sensor_key(sensor_key)
        self._state_topic.publish(
            ExternalSensorStateEvent(sensor_key=sensor_key, value=value)
        )

    def clear_value(self, sensor_key: str) -> None:
        _split_sensor_key(sensor_key)
        self._state_topic.publish(
            ExternalSensorStateEvent(sensor_key=sensor_key, value=None)
        )

    def observable_acceleration(self) -> Subscribable[Acceleration | None]:
        return cast(
            Subscribable[Acceleration | None],
            self._accelerometer_stream.start_with(self._accelerometer_stream.value),
        )

    def close(self) -> None:
        self._state_subscription.dispose()

    def _apply_state(self, event: ExternalSensorStateEvent) -> None:
        peripheral_id, path = _split_sensor_key(event.sensor_key)
        with self._lock:
            snapshot = self._peripheral_snapshots.setdefault(peripheral_id, {})
            if event.value is None:
                self._values.pop(event.sensor_key, None)
                _delete_snapshot_value(snapshot, path)
                if not snapshot:
                    self._peripheral_snapshots.pop(peripheral_id, None)
            else:
                self._values[event.sensor_key] = event.value
                _set_snapshot_value(snapshot, path, event.value)
            acceleration = self._resolve_acceleration_locked()
            published_snapshot = dict(snapshot)
        self._accelerometer_stream.emit(acceleration)
        self._debug_tap.publish(
            stage=InputDebugStage.LOGICAL,
            stream_name=EXTERNAL_SENSOR_STREAM_NAME,
            source_id=peripheral_id,
            payload=published_snapshot,
            upstream_ids=(EXTERNAL_SENSOR_SOURCE,),
        )

    def _resolve_acceleration_locked(self) -> Acceleration | None:
        matching = {
            path: value
            for sensor_key, value in self._values.items()
            for peripheral_id, path in [_split_sensor_key(sensor_key)]
            if "accelerometer" in peripheral_id.lower() and path in ACCELEROMETER_PATHS
        }
        if not matching:
            return None
        return Acceleration(
            x=matching.get("x", 0.0),
            y=matching.get("y", 0.0),
            z=matching.get("z", 0.0),
        )


def _split_sensor_key(sensor_key: str) -> tuple[str, str]:
    peripheral_id, separator, path = sensor_key.rpartition(":")
    if not separator or not peripheral_id or not path:
        msg = f"Invalid sensor key: {sensor_key}"
        raise ValueError(msg)
    return peripheral_id, path


def _set_snapshot_value(snapshot: dict[str, Any], path: str, value: float) -> None:
    parts = path.split(".")
    current: dict[str, Any] = snapshot
    for part in parts[:-1]:
        existing = current.get(part)
        if not isinstance(existing, dict):
            existing = {}
            current[part] = existing
        current = existing
    current[parts[-1]] = value


def _delete_snapshot_value(snapshot: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    current: dict[str, Any] = snapshot
    parents: list[tuple[dict[str, Any], str]] = []
    for part in parts[:-1]:
        existing = current.get(part)
        if not isinstance(existing, dict):
            return
        parents.append((current, part))
        current = existing
    current.pop(parts[-1], None)
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            parent.pop(key, None)
