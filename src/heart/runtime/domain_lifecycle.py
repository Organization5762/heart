"""Bounded Heart-owned domain transitions on named PubSub topics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import final

from manyfold.architecture import PubSub, PubSubTopic

HEART_RUNTIME_PUBSUB = "heart"
PERIPHERAL_LIFECYCLE_TOPIC = "heart.lifecycle.peripheral"
INPUT_LIFECYCLE_TOPIC = "heart.lifecycle.input"
SCENE_LIFECYCLE_TOPIC = "heart.lifecycle.scene"
RENDERER_LIFECYCLE_TOPIC = "heart.lifecycle.renderer"
SENSOR_LIFECYCLE_TOPIC = "heart.lifecycle.sensor"
PIPELINE_LIFECYCLE_TOPIC = "heart.lifecycle.pipeline"


class HeartLifecycleKind(str, Enum):
    """Stable application transitions that the ManyFold mesh cannot infer."""

    PERIPHERAL_ATTACHED = "peripheral_attached"
    PERIPHERAL_DETACHED = "peripheral_detached"
    INPUT_SOURCE_ACTIVE = "input_source_active"
    INPUT_SOURCE_INACTIVE = "input_source_inactive"
    SCENE_SELECTED = "scene_selected"
    SCENE_ACTIVATED = "scene_activated"
    SCENE_DEACTIVATED = "scene_deactivated"
    RENDERER_STARTED = "renderer_started"
    RENDERER_STOPPED = "renderer_stopped"
    RENDERER_FAILED = "renderer_failed"
    SENSOR_ONLINE = "sensor_online"
    SENSOR_STALE = "sensor_stale"
    SENSOR_OFFLINE = "sensor_offline"
    FRAME_PIPELINE_PRESSURE = "frame_pipeline_pressure"
    FRAME_PIPELINE_RECOVERED = "frame_pipeline_recovered"
    AUDIO_PIPELINE_PRESSURE = "audio_pipeline_pressure"
    AUDIO_PIPELINE_RECOVERED = "audio_pipeline_recovered"


class HeartLifecycleReason(str, Enum):
    """Stable causes for Heart-owned application transitions."""

    DETECTED = "detected"
    REPLACED = "replaced"
    SHUTDOWN = "shutdown"
    NAVIGATION = "navigation"
    DIRECT_SELECTION = "direct_selection"
    INITIALIZED = "initialized"
    RESET = "reset"
    PROCESSING_FAILED = "processing_failed"
    SAMPLE_RECEIVED = "sample_received"
    TTL_EXPIRED = "ttl_expired"
    SOURCE_CLEARED = "source_cleared"
    CAPACITY = "capacity"
    RECOVERED = "recovered"


@final
@dataclass(frozen=True, slots=True)
class HeartDomainTransition:
    """One deterministic, correlation-bearing Heart application transition."""

    event_id: str
    kind: str
    entity_id: str
    reason: str
    correlation_id: str
    revision: int
    related_id: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        HeartLifecycleKind(self.kind)
        HeartLifecycleReason(self.reason)
        for name, value in (
            ("event_id", self.event_id),
            ("entity_id", self.entity_id),
            ("correlation_id", self.correlation_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.revision < 1:
            raise ValueError("revision must be positive")

    @property
    def event_kind(self) -> HeartLifecycleKind:
        return HeartLifecycleKind(self.kind)

    @property
    def event_reason(self) -> HeartLifecycleReason:
        return HeartLifecycleReason(self.reason)


def peripheral_lifecycle_topic() -> PubSub:
    return _topic(PERIPHERAL_LIFECYCLE_TOPIC)


def input_lifecycle_topic() -> PubSub:
    return _topic(INPUT_LIFECYCLE_TOPIC)


def scene_lifecycle_topic() -> PubSub:
    return _topic(SCENE_LIFECYCLE_TOPIC)


def renderer_lifecycle_topic() -> PubSub:
    return _topic(RENDERER_LIFECYCLE_TOPIC)


def sensor_lifecycle_topic() -> PubSub:
    return _topic(SENSOR_LIFECYCLE_TOPIC)


def pipeline_lifecycle_topic() -> PubSub:
    return _topic(PIPELINE_LIFECYCLE_TOPIC)


def domain_lifecycle_topics() -> tuple[PubSub, ...]:
    return (
        peripheral_lifecycle_topic(),
        input_lifecycle_topic(),
        scene_lifecycle_topic(),
        renderer_lifecycle_topic(),
        sensor_lifecycle_topic(),
        pipeline_lifecycle_topic(),
    )


@final
class HeartLifecycleEmitter:
    """Publish only semantic transitions with deterministic per-entity
    revisions."""

    def __init__(self, topic: PubSub) -> None:
        self._topic = topic
        self._revisions: dict[str, int] = {}
        self._lock = Lock()

    def emit(
        self,
        kind: HeartLifecycleKind,
        entity_id: str,
        reason: HeartLifecycleReason,
        *,
        correlation_id: str | None = None,
        related_id: str = "",
        detail: str = "",
    ) -> HeartDomainTransition:
        with self._lock:
            revision = self._revisions.get(entity_id, 0) + 1
            self._revisions[entity_id] = revision
        resolved_correlation = correlation_id or (
            f"{kind.value}:{entity_id}:{revision}"
        )
        transition = HeartDomainTransition(
            event_id=(
                f"{resolved_correlation}:{kind.value}:{revision}"
            ),
            kind=kind.value,
            entity_id=entity_id,
            reason=reason.value,
            correlation_id=resolved_correlation,
            revision=revision,
            related_id=related_id,
            detail=detail,
        )
        self._topic.publish(
            transition,
            key=transition.event_id,
        )
        return transition


def _topic(name: str) -> PubSub:
    return PubSubTopic(
        name,
        schema=HeartDomainTransition,
        pubsub=HEART_RUNTIME_PUBSUB,
    )


__all__ = [
    "HeartDomainTransition",
    "HeartLifecycleEmitter",
    "HeartLifecycleKind",
    "HeartLifecycleReason",
    "INPUT_LIFECYCLE_TOPIC",
    "PERIPHERAL_LIFECYCLE_TOPIC",
    "PIPELINE_LIFECYCLE_TOPIC",
    "RENDERER_LIFECYCLE_TOPIC",
    "SCENE_LIFECYCLE_TOPIC",
    "SENSOR_LIFECYCLE_TOPIC",
    "domain_lifecycle_topics",
    "input_lifecycle_topic",
    "peripheral_lifecycle_topic",
    "pipeline_lifecycle_topic",
    "renderer_lifecycle_topic",
    "scene_lifecycle_topic",
    "sensor_lifecycle_topic",
]
