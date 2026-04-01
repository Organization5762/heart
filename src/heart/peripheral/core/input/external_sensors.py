from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from reactivex.subject import BehaviorSubject

from heart.peripheral.core.input.debug import InputDebugStage, InputDebugTap
from heart.peripheral.sensor import Acceleration

ACCELEROMETER_PATHS = frozenset({"x", "y", "z"})
EXTERNAL_SENSOR_STREAM_NAME = "beats.sensor.control"
EXTERNAL_SENSOR_SOURCE = "beats.sensor"


@dataclass(frozen=True, slots=True)
class ExternalSensorUpdate:
    sensor_key: str
    peripheral_id: str
    path: str
    value: float | None


class ExternalSensorHub:
    def __init__(self, debug_tap: InputDebugTap) -> None:
        self._debug_tap = debug_tap
        self._lock = Lock()
        self._values: dict[str, float] = {}
        self._peripheral_snapshots: dict[str, dict[str, Any]] = {}
        self._accelerometer_subject: BehaviorSubject[Acceleration | None] = (
            BehaviorSubject(None)
        )

    def set_value(self, sensor_key: str, value: float) -> None:
        peripheral_id, path = _split_sensor_key(sensor_key)
        with self._lock:
            self._values[sensor_key] = value
            snapshot = self._peripheral_snapshots.setdefault(peripheral_id, {})
            _set_snapshot_value(snapshot, path, value)
            acceleration = self._resolve_acceleration_locked()
            published_snapshot = dict(snapshot)
        self._accelerometer_subject.on_next(acceleration)
        self._debug_tap.publish(
            stage=InputDebugStage.LOGICAL,
            stream_name=EXTERNAL_SENSOR_STREAM_NAME,
            source_id=peripheral_id,
            payload=published_snapshot,
            upstream_ids=(EXTERNAL_SENSOR_SOURCE,),
        )

    def clear_value(self, sensor_key: str) -> None:
        peripheral_id, path = _split_sensor_key(sensor_key)
        with self._lock:
            self._values.pop(sensor_key, None)
            snapshot = self._peripheral_snapshots.setdefault(peripheral_id, {})
            _delete_snapshot_value(snapshot, path)
            if not snapshot:
                self._peripheral_snapshots.pop(peripheral_id, None)
            acceleration = self._resolve_acceleration_locked()
            published_snapshot = dict(snapshot)
        self._accelerometer_subject.on_next(acceleration)
        self._debug_tap.publish(
            stage=InputDebugStage.LOGICAL,
            stream_name=EXTERNAL_SENSOR_STREAM_NAME,
            source_id=peripheral_id,
            payload=published_snapshot,
            upstream_ids=(EXTERNAL_SENSOR_SOURCE,),
        )

    def observable_acceleration(self) -> BehaviorSubject[Acceleration | None]:
        return self._accelerometer_subject

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
