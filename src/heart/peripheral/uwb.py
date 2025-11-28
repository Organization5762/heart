"""Helpers for translating UWB ranging data into automation events.

The ``docs/planning/uwb_peripheral_rollout.md`` plan calls for an adapter that
consumes raw ranging payloads and emits zone entry/exit events with hysteresis
so downstream automations do not thrash when a tag hovers near a boundary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import reactivex
from reactivex import operators as ops

from heart.peripheral.core import Input
from heart.utilities.logging import get_logger


def _to_float(value: object, *, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Vector components must be numeric") from exc
    raise TypeError("Vector components must be numeric")

logger = get_logger(__name__)


Vector3 = tuple[float, float, float]


def _normalize_vector(value: Sequence[float]) -> Vector3:
    components = [float(component) for component in value]
    if len(components) == 2:
        components.append(0.0)
    if len(components) != 3:
        raise ValueError("Vector must contain two or three components")
    return (components[0], components[1], components[2])


def _mapping_to_vector(mapping: Mapping[str, object]) -> Vector3:
    try:
        x = _to_float(mapping.get("x", 0.0))
        y = _to_float(mapping.get("y", 0.0))
        z = _to_float(mapping.get("z"), default=0.0)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
        raise ValueError("Position components must be numeric") from exc
    return (x, y, z)


@dataclass(slots=True, frozen=True)
class UwbZoneDefinition:
    """Description of a spatial zone used for automation triggers."""

    zone_id: str
    center: Vector3
    enter_radius: float
    exit_radius: float | None = None

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("zone_id must be a non-empty string")
        if self.enter_radius <= 0:
            raise ValueError("enter_radius must be positive")
        if self.exit_radius is not None and self.exit_radius < self.enter_radius:
            raise ValueError("exit_radius must be greater than or equal to enter_radius")


@dataclass(slots=True)
class _Observation:
    tag_id: str
    position: Vector3
    payload: Mapping[str, object]


class UwbZoneTracker:
    """Translate UWB ranging events into zone entry/exit notifications."""

    DEFAULT_EVENT_TYPE = "uwb.ranging_event"

    def __init__(
        self,
        zones: Iterable[UwbZoneDefinition],
        *,
        event_type: str = DEFAULT_EVENT_TYPE,
        exit_margin: float = 0.15,
        priority: int = 0,
    ) -> None:
        if exit_margin < 0:
            raise ValueError("exit_margin must be non-negative")

        self._zones: dict[str, UwbZoneDefinition] = {}
        for zone in zones:
            self._zones[zone.zone_id] = UwbZoneDefinition(
                zone.zone_id,
                _normalize_vector(zone.center),
                zone.enter_radius,
                zone.exit_radius,
            )

        self._event_type = event_type
        self._exit_margin = exit_margin
        self._priority = priority
        self.zone_state: Any = None

        self._memberships: MutableMapping[str, MutableMapping[str, bool]] = {}
        self._last_positions: MutableMapping[str, Vector3] = {}

    def get_active_zones(self, tag_id: str) -> tuple[str, ...]:
        """Return the zones currently occupied by ``tag_id``."""

        membership = self._memberships.get(tag_id)
        if not membership:
            return ()
        return tuple(sorted(zone_id for zone_id, inside in membership.items() if inside))

    def get_last_position(self, tag_id: str) -> Vector3 | None:
        return self._last_positions.get(tag_id)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def _handle_ranging_event(self, event: Input) -> None:
        observation = self._parse_observation(event)
        if observation is None:
            return

        self._last_positions[observation.tag_id] = observation.position
        for zone in self._zones.values():
            self._evaluate_zone(observation, zone)

    def _parse_observation(self, event: Input) -> _Observation | None:
        payload = event.data
        if not isinstance(payload, Mapping):
            logger.debug("Ignoring non-mapping UWB payload: %s", payload)
            return None

        tag_id = self._extract_tag_id(payload)
        position_raw = (
            payload.get("position")
            or payload.get("coordinates")
            or payload.get("location")
        )
        if position_raw is None:
            logger.debug("Ignoring UWB payload without coordinates: %s", payload)
            return None

        try:
            if isinstance(position_raw, Mapping):
                position = _mapping_to_vector(position_raw)
            elif isinstance(position_raw, Sequence):
                position = _normalize_vector(position_raw)
            else:
                raise TypeError
        except (TypeError, ValueError):
            logger.debug("Ignoring malformed UWB coordinates: %s", position_raw)
            return None

        return _Observation(
            tag_id=tag_id,
            position=position,
            payload=payload,
        )

    def _extract_tag_id(self, payload: Mapping[str, object]) -> str:
        for key in ("tag_id", "device_id", "peripheral_id", "tracker_id", "anchor_id"):
            value = payload.get(key)
            if value is not None:
                return str(value)
        raise ValueError("")

    def _evaluate_zone(self, observation: _Observation, zone: UwbZoneDefinition) -> None:
        membership = self._memberships.setdefault(observation.tag_id, {})
        inside = membership.get(zone.zone_id, False)
        distance = self._distance(observation.position, zone.center)

        exit_radius = (
            zone.exit_radius
            if zone.exit_radius is not None
            else zone.enter_radius + self._exit_margin
        )

        if not inside and distance <= zone.enter_radius:
            membership[zone.zone_id] = True
            self._emit_zone_event(
                "uwb.zone.entry", observation, zone, distance
            )
        elif inside and distance >= exit_radius:
            membership[zone.zone_id] = False
            self._emit_zone_event(
                "uwb.zone.exit", observation, zone, distance
            )

    def _distance(self, a: Vector3, b: Vector3) -> float:
        return math.dist(a, b)

    def _emit_zone_event(
        self,
        event_type: str,
        observation: _Observation,
        zone: UwbZoneDefinition,
        distance: float,
    ) -> None:
        self.zone_state = {
            "tag_id": observation.tag_id,
            "zone_id": zone.zone_id,
            "distance": distance,
            "position": {
                "x": observation.position[0],
                "y": observation.position[1],
                "z": observation.position[2],
            },
            "zone_center": {
                "x": zone.center[0],
                "y": zone.center[1],
                "z": zone.center[2],
            },
            "enter_radius": zone.enter_radius,
            "exit_radius": (
                zone.exit_radius
                if zone.exit_radius is not None
                else zone.enter_radius + self._exit_margin
            ),
            "raw": observation.payload,
        }

    def _event_stream(
        self
    ) -> reactivex.Observable[dict[str, Any] | None]:
        return reactivex.interval(timedelta(milliseconds=10)).pipe(
            ops.map(lambda _: self.zone_state),
            ops.distinct_until_changed(lambda x: x)
        )
