"""Real Heart role process for ManyFold's consumer qualification gate."""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Mapping
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Any, final

from manyfold.architecture import (MeshConfig, MeshDurabilityConfig,
                                   MeshLifecycleEvent, MeshPeerHealth,
                                   NodeIdentity, PeerDiscovery,
                                   PubSubCallbackSubscription, ReconnectPolicy,
                                   TcpAddress, TransportConfig, TransportMesh,
                                   TransportSecurity)
from manyfold.cluster import (ClusterConfig, CommittedCommand, MemberConfig,
                              PersistentRaftCoordinator)

from heart.peripheral.core.input.events import (FRAME_TICK_TOPIC,
                                                INPUT_EVENT_TOPIC, InputEvent)
from heart.peripheral.core.input.external_sensors import (
    EXTERNAL_SENSOR_STATE_TOPIC, SENSOR_OFFLINE_SECONDS, SENSOR_STALE_SECONDS,
    ExternalSensorStateEvent)
from heart.peripheral.core.input.frame import FrameTick
from heart.peripheral.core.input.profiles.navigation import (NAVIGATION_TOPIC,
                                                             NavigationEvent)
from heart.peripheral.led_matrix import HEART_RENDERED_FRAME_TOPIC
from heart.peripheral.microphone import HEART_MICROPHONE_SAMPLE_TOPIC
from heart.runtime.manyfold_node import bind_heart_topics, heart_topic_handles
from heart.world import (ActiveMode, WorldDevice, WorldDimensions,
                         WorldPosition, WorldState, put_device_command,
                         select_mode_command)

_SCHEMA_VERSION = 1
_MAX_OPERATIONS = 1024
_MAX_EFFECTS = 128
_SENSOR_PREFIX = "qualification:"
_WORLD_OWNER_ID = "qualification-device"
_WORLD_BOOTSTRAP_OPERATION_ID = "qualification-bootstrap-device"


@final
class QualificationRole:
    """One bounded, observable Heart application role on a real mesh."""

    def __init__(self, payload: Mapping[str, object]) -> None:
        self._role_id = _text(payload, "role_id")
        self._role_kind = _text(payload, "role_kind")
        self._node_id = _text(payload, "node_id")
        self._state_directory = Path(_text(payload, "state_directory"))
        self._journal_directory = Path(_text(payload, "journal_directory"))
        self._state_directory.mkdir(parents=True, exist_ok=True)
        self._journal_directory.mkdir(parents=True, exist_ok=True)
        self._state_path = self._state_directory / "qualification-state.json"
        self._lock = Lock()
        self._operations: dict[str, dict[str, object]] = {}
        self._expected_operations: set[str] = set()
        self._effects: dict[tuple[str, str], dict[str, object]] = {}
        self._subscriptions: list[PubSubCallbackSubscription] = []
        self._lifecycle_after_sequence = 0
        self._closed = False
        self._sensor_key: str | None = None
        self._sensor_updated_at: float | None = None
        self._sensor_status: str | None = None
        self._coordinator: PersistentRaftCoordinator | None = None
        self._coordination_after_sequence = 0
        self._world_state = WorldState()
        self._load_state()

        transport = _transport_config()
        self._mesh = TransportMesh(
            _identity(payload),
            connector_config=transport,
            listener_config=transport,
            config=MeshConfig(
                max_peers=4,
                max_subscriptions=4096,
                duplicate_window=8192,
                publication_queue_limit=64,
                lifecycle_event_limit=4096,
            ),
            durability=MeshDurabilityConfig(
                self._journal_directory,
                hard_peer_items=1024,
                hard_peer_bytes=64 * 1024 * 1024,
                dedupe_retention_seconds=30.0,
            ),
        )
        self._bindings = bind_heart_topics(self._mesh)
        self._topics = {topic.topic: topic for topic in heart_topic_handles()}
        self._install_application_observers()
        self._configure_mesh(payload)
        self._configure_coordinator(payload)

    @property
    def role_id(self) -> str:
        return self._role_id

    def handle(
        self, operation: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        if operation == "ready":
            return self._ready()
        if operation == "stimulus":
            return self._stimulus(payload)
        if operation == "observe":
            return self._observe()
        if operation == "coordinator_status":
            return self._coordinator_status()
        if operation == "bootstrap_world":
            return self._bootstrap_world()
        if operation == "close":
            return self.close()
        raise ValueError(f"unknown role operation {operation!r}")

    def close(self) -> dict[str, object]:
        if self._closed:
            return {
                "role_id": self._role_id,
                "exited": True,
                "lifecycle_batch": self._empty_lifecycle_batch(),
            }
        for subscription in self._subscriptions:
            subscription.dispose()
        self._subscriptions.clear()
        if self._coordinator is not None:
            self._coordinator.close()
        self._mesh.close()
        lifecycle_batch = self._lifecycle_batch()
        self._closed = True
        return {
            "role_id": self._role_id,
            "exited": True,
            "lifecycle_batch": lifecycle_batch,
        }

    def _ready(self) -> dict[str, object]:
        mesh = self._mesh.health()
        coordinator = self._coordinator
        return {
            "role_id": self._role_id,
            "ready": mesh.connected_peers == 2
            and (coordinator is None or coordinator.status().ready),
            "connected_peers": mesh.connected_peers,
            "coordinator_ready": (
                None if coordinator is None else coordinator.status().ready
            ),
        }

    def _stimulus(self, payload: Mapping[str, object]) -> dict[str, object]:
        operation_id = _text(payload, "operation_id")
        kind = _text(payload, "kind")
        payload_label = _text(payload, "payload_label")
        value = _mapping(payload.get("value"), "stimulus value")
        with self._lock:
            if (
                operation_id not in self._expected_operations
                and len(self._expected_operations) >= _MAX_OPERATIONS
            ):
                raise RuntimeError("qualification operation bound is full")
            self._expected_operations.add(operation_id)

        if kind == "navigation":
            direction = str(value.get("direction", "right"))
            step = -1 if direction == "left" else 1
            self._topics[NAVIGATION_TOPIC].publish(
                NavigationEvent(
                    kind="browse",
                    source=f"qualification:{self._role_id}",
                    step=step,
                    request_id=operation_id,
                ),
                key=operation_id,
            )
        elif kind == "sensor_sample":
            sensor_key = f"{_SENSOR_PREFIX}{operation_id}"
            self._sensor_key = sensor_key
            reading = value.get("reading", 0)
            if isinstance(reading, bool) or not isinstance(reading, int | float):
                raise ValueError("sensor reading must be numeric")
            self._topics[EXTERNAL_SENSOR_STATE_TOPIC].publish(
                ExternalSensorStateEvent(sensor_key, float(reading)),
                key=sensor_key,
            )
        elif kind == "frame_tick":
            frame_index = value.get("frame", 0)
            if isinstance(frame_index, bool) or not isinstance(frame_index, int):
                raise ValueError("frame index must be an integer")
            self._topics[FRAME_TICK_TOPIC].publish(
                FrameTick(
                    frame_index=frame_index,
                    delta_ms=1.0,
                    delta_s=0.001,
                    monotonic_s=time.monotonic(),
                    fps=120.0,
                ),
                key=f"{self._node_id}:{FRAME_TICK_TOPIC}",
            )
        elif kind == "render_frame":
            self._publish_raw(
                HEART_RENDERED_FRAME_TOPIC,
                operation_id,
                payload_label,
                value,
                key=f"{self._node_id}:{HEART_RENDERED_FRAME_TOPIC}:display",
            )
        elif kind == "audio_sample":
            self._publish_raw(
                HEART_MICROPHONE_SAMPLE_TOPIC,
                operation_id,
                payload_label,
                value,
                key=(
                    f"{self._node_id}:{HEART_MICROPHONE_SAMPLE_TOPIC}:"
                    "microphone:default"
                ),
            )
        elif kind == "debug_input":
            self._topics[INPUT_EVENT_TOPIC].publish(
                InputEvent.from_payload(
                    event_type="input.logical.qualification",
                    source_id=self._role_id,
                    stream_name="qualification",
                    stage="logical",
                    payload={
                        "operation_id": operation_id,
                        "payload_label": payload_label,
                        "value": value,
                    },
                    timestamp_monotonic=time.monotonic(),
                ),
                key=f"logical:qualification:{self._role_id}",
            )
        elif kind in {"world_write", "device_write"}:
            return self._commit_coordination(
                operation_id,
                kind,
                payload_label,
                value,
            )
        else:
            raise ValueError(f"unknown stimulus kind {kind!r}")
        return {"accepted": True, "operation_id": operation_id}

    def _observe(self) -> dict[str, object]:
        self._refresh_world_state()
        diagnostics = self._mesh.durable_topic_diagnostics()
        queue_depth = self._mesh.health().publications_queued + sum(
            item.outbox_items for item in diagnostics
        )
        sensor_status = None
        stale_age_ms = None
        if self._sensor_key is not None and self._sensor_updated_at is not None:
            stale_age_ms = max(
                0,
                round((time.monotonic() - self._sensor_updated_at) * 1000),
            )
            if stale_age_ms >= round(SENSOR_OFFLINE_SECONDS * 1000):
                self._sensor_status = "offline"
            elif stale_age_ms >= round(SENSOR_STALE_SECONDS * 1000):
                self._sensor_status = "stale"
            sensor_status = self._sensor_status
        with self._lock:
            operations = list(self._operations.values())
            effects = list(self._effects.values())
        state_revision, state_digest = self._state_revision_digest()
        return {
            "role": {
                "role_id": self._role_id,
                "serving": not self._closed,
                "lifecycle_after_sequence": self._lifecycle_after_sequence,
                "state_revision": state_revision,
                "state_digest": state_digest,
                "stale_age_ms": stale_age_ms,
                "sensor_status": sensor_status,
                "queue_depth": queue_depth,
            },
            "operations": operations,
            "user_effects": effects,
            "lifecycle_batch": self._lifecycle_batch(),
            "topic_diagnostics": [
                {
                    **asdict(item),
                    "delivery_class": item.delivery_class.value,
                }
                for item in diagnostics
            ],
            "mesh_health": asdict(self._mesh.health()),
            "peer_health": [_peer_health(peer) for peer in self._mesh.peer_health()],
        }

    def _coordinator_status(self) -> dict[str, object]:
        coordinator = self._coordinator
        if coordinator is None:
            return {"role_id": self._role_id, "coordinator": False}
        return {
            "role_id": self._role_id,
            "coordinator": True,
            "status": asdict(coordinator.status()),
        }

    def _bootstrap_world(self) -> dict[str, object]:
        coordinator = self._coordinator
        if coordinator is None:
            raise RuntimeError("world bootstrap requires a coordinator role")
        committed = coordinator.commit(
            put_device_command(
                _WORLD_BOOTSTRAP_OPERATION_ID,
                _qualification_device(revision=0),
            ),
            timeout_seconds=2.0,
        )
        self._refresh_world_state()
        return {
            "committed_id": committed.command_id,
            "revision": committed.sequence,
        }

    def _configure_mesh(self, payload: Mapping[str, object]) -> None:
        listener = _mapping(payload.get("listener"), "listener")
        connector = _mapping(payload.get("connector"), "connector")
        self._mesh.listen(
            _text(listener, "peer_node_id"),
            TcpAddress("127.0.0.1", _integer(listener, "port")),
        )
        self._mesh.apply_discovery(
            (
                PeerDiscovery(
                    _text(connector, "peer_node_id"),
                    TcpAddress("127.0.0.1", _integer(connector, "port")),
                ),
            )
        )

    def _configure_coordinator(self, payload: Mapping[str, object]) -> None:
        value = payload.get("coordinator")
        if value is None:
            return
        coordinator = _mapping(value, "coordinator")
        config = _cluster_config(_mapping(coordinator.get("config"), "config"))
        self._coordinator = PersistentRaftCoordinator(
            config,
            self._node_id,
            Path(_text(coordinator, "state_directory")),
        )

    def _install_application_observers(self) -> None:
        if self._role_kind == "navigation_input_ingress":
            self._subscriptions.append(
                self._topics[NAVIGATION_TOPIC].subscribe(self._apply_navigation)
            )
            self._subscriptions.append(
                self._topics[INPUT_EVENT_TOPIC].subscribe(self._apply_debug)
            )
        elif self._role_kind == "low_rate_sensor_ingress":
            self._subscriptions.append(
                self._topics[EXTERNAL_SENSOR_STATE_TOPIC].subscribe(self._apply_sensor)
            )
        elif self._role_kind == "renderer":
            self._subscriptions.append(
                self._topics[FRAME_TICK_TOPIC].subscribe(self._apply_frame_tick)
            )
        elif self._role_kind == "audio_processor":
            self._subscriptions.append(
                self._topics[HEART_MICROPHONE_SAMPLE_TOPIC].subscribe(self._apply_audio)
            )
        elif self._role_kind == "pixel_sink":
            self._subscriptions.append(
                self._topics[HEART_RENDERED_FRAME_TOPIC].subscribe(
                    self._apply_rendered_frame
                )
            )

    def _apply_navigation(self, row: Any) -> None:
        operation_id = str(row.request_id)
        if self._is_expected(operation_id):
            self._record_operation(
                operation_id,
                committed_id=operation_id,
                effect="navigation_action",
                payload_label=str(row.kind),
            )

    def _apply_sensor(self, row: Any) -> None:
        sensor_key = str(row.sensor_key)
        if not sensor_key.startswith(_SENSOR_PREFIX):
            return
        operation_id = sensor_key.removeprefix(_SENSOR_PREFIX)
        if self._is_expected(operation_id):
            self._sensor_key = sensor_key
            self._sensor_updated_at = time.monotonic()
            self._sensor_status = "online"
            self._record_operation(
                operation_id,
                committed_id=operation_id,
                effect="sensor_value",
                payload_label=sensor_key,
            )

    def _apply_frame_tick(self, row: Any) -> None:
        with self._lock:
            expected = tuple(self._expected_operations)
        for operation_id in expected:
            if operation_id.startswith("frame-tick"):
                self._record_operation(
                    operation_id,
                    committed_id=operation_id,
                    effect="frame_tick_seen",
                    payload_label=str(row.frame_index),
                )

    def _apply_debug(self, row: Any) -> None:
        try:
            payload = json.loads(str(row.payload_json))
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return
        operation_id = payload.get("operation_id")
        payload_label = payload.get("payload_label")
        if (
            isinstance(operation_id, str)
            and isinstance(payload_label, str)
            and self._is_expected(operation_id)
        ):
            self._record_operation(
                operation_id,
                committed_id=operation_id,
                effect="debug_input_seen",
                payload_label=payload_label,
            )

    def _apply_audio(self, row: Any) -> None:
        self._apply_raw_effect(row, "audio_processed")

    def _apply_rendered_frame(self, row: Any) -> None:
        self._apply_raw_effect(row, "frame_displayed")

    def _apply_raw_effect(self, row: Any, effect: str) -> None:
        try:
            value = json.loads(bytes(row.payload))
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(value, dict):
            return
        operation_id = value.get("operation_id")
        payload_label = value.get("payload_label")
        if not isinstance(operation_id, str) or not isinstance(payload_label, str):
            return
        if self._is_expected(operation_id):
            self._record_operation(
                operation_id,
                committed_id=operation_id,
                effect=effect,
                payload_label=payload_label,
            )
            return
        self._record_effect(effect, operation_id, payload_label)

    def _commit_coordination(
        self,
        operation_id: str,
        kind: str,
        payload_label: str,
        value: Mapping[str, object],
    ) -> dict[str, object]:
        coordinator = self._coordinator
        if coordinator is None:
            raise RuntimeError("coordination stimulus requires a coordinator role")
        revision = value.get("revision", 1)
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise ValueError("coordination revision must be an integer")
        if kind == "world_write":
            command = select_mode_command(
                operation_id,
                ActiveMode(
                    mode_id=payload_label,
                    configuration_id=f"qualification-{revision}",
                    owner_device_id=_WORLD_OWNER_ID,
                ),
            )
        else:
            command = put_device_command(
                operation_id,
                _qualification_device(revision=revision),
            )
        committed = coordinator.commit(
            command,
            timeout_seconds=2.0,
        )
        self._record_operation(
            operation_id,
            committed_id=committed.command_id,
            effect=kind,
            payload_label=payload_label,
        )
        return {
            "accepted": True,
            "operation_id": operation_id,
            "committed_id": committed.command_id,
            "revision": committed.sequence,
        }

    def _refresh_world_state(self) -> None:
        coordinator = self._coordinator
        if coordinator is None:
            return
        commands = coordinator.read_log(
            after_sequence=self._coordination_after_sequence
        )
        for command in commands:
            self._world_state.apply(command)
            self._record_committed_operation(command)
            self._coordination_after_sequence = command.sequence

    def _record_committed_operation(self, command: CommittedCommand) -> None:
        if command.command_id == _WORLD_BOOTSTRAP_OPERATION_ID:
            return
        with self._lock:
            existing = self._operations.get(command.command_id)
            if existing is None:
                self._operations[command.command_id] = {
                    "operation_id": command.command_id,
                    "status": "committed",
                    "committed_id": command.command_id,
                    "apply_count": 1,
                }
        self._persist_state()

    def _state_revision_digest(self) -> tuple[int, str]:
        coordinator = self._coordinator
        if coordinator is not None:
            commands = coordinator.read_log()
            coordination_value = [command.to_dict() for command in commands]
            return self._world_state.revision, _semantic_digest(coordination_value)
        with self._lock:
            local_value = {
                "operations": sorted(
                    self._operations.values(),
                    key=lambda item: str(item["operation_id"]),
                ),
                "effects": sorted(
                    self._effects.values(),
                    key=lambda item: (
                        str(item["effect"]),
                        str(item["operation_id"]),
                    ),
                ),
            }
        return len(local_value["operations"]), _semantic_digest(local_value)

    def _record_operation(
        self,
        operation_id: str,
        *,
        committed_id: str,
        effect: str,
        payload_label: str,
    ) -> None:
        with self._lock:
            existing = self._operations.get(operation_id)
            if existing is None:
                if len(self._operations) >= _MAX_OPERATIONS:
                    raise RuntimeError("qualification operation bound is full")
                self._operations[operation_id] = {
                    "operation_id": operation_id,
                    "status": "applied",
                    "committed_id": committed_id,
                    "apply_count": 1,
                }
            self._record_effect_locked(
                effect,
                operation_id,
                payload_label,
            )
        self._persist_state()

    def _record_effect(
        self,
        effect: str,
        operation_id: str,
        payload_label: str,
    ) -> None:
        with self._lock:
            self._record_effect_locked(effect, operation_id, payload_label)
        self._persist_state()

    def _record_effect_locked(
        self,
        effect: str,
        operation_id: str,
        payload_label: str,
    ) -> None:
        key = (effect, self._role_id)
        if key not in self._effects and len(self._effects) >= _MAX_EFFECTS:
            raise RuntimeError("qualification effect bound is full")
        self._effects[key] = {
            "effect": effect,
            "role_id": self._role_id,
            "operation_id": operation_id,
            "payload_label": payload_label,
        }

    def _publish_raw(
        self,
        topic: str,
        operation_id: str,
        payload_label: str,
        value: Mapping[str, object],
        *,
        key: str,
    ) -> None:
        payload = json.dumps(
            {
                "operation_id": operation_id,
                "payload_label": payload_label,
                "value": dict(value),
            },
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        self._topics[topic].publish(payload, key=key)

    def _is_expected(self, operation_id: str) -> bool:
        with self._lock:
            return operation_id in self._expected_operations

    def _lifecycle_batch(self) -> dict[str, object]:
        before = self._lifecycle_after_sequence
        events = self._mesh.lifecycle_events(after_sequence=before)
        after = events[-1].sequence if events else before
        self._lifecycle_after_sequence = after
        return {
            "role_id": self._role_id,
            "cursor_before": before,
            "cursor_after": after,
            "events": [_lifecycle_event(event) for event in events],
        }

    def _empty_lifecycle_batch(self) -> dict[str, object]:
        return {
            "role_id": self._role_id,
            "cursor_before": self._lifecycle_after_sequence,
            "cursor_after": self._lifecycle_after_sequence,
            "events": [],
        }

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return
        value = json.loads(self._state_path.read_text(encoding="utf-8"))
        state = _mapping(value, "qualification state")
        operations = state.get("operations", [])
        effects = state.get("effects", [])
        if not isinstance(operations, list) or not isinstance(effects, list):
            raise ValueError("qualification state lists are invalid")
        for item in operations:
            operation = _mapping(item, "operation")
            operation_id = _text(operation, "operation_id")
            self._operations[operation_id] = dict(operation)
        for item in effects:
            effect = _mapping(item, "effect")
            key = (_text(effect, "effect"), _text(effect, "role_id"))
            self._effects[key] = dict(effect)

    def _persist_state(self) -> None:
        with self._lock:
            value = {
                "schema_version": _SCHEMA_VERSION,
                "operations": sorted(
                    self._operations.values(),
                    key=lambda item: str(item["operation_id"]),
                ),
                "effects": sorted(
                    self._effects.values(),
                    key=lambda item: (
                        str(item["effect"]),
                        str(item["operation_id"]),
                    ),
                ),
            }
        temporary = self._state_path.with_name(
            f".{self._state_path.name}.{os.getpid()}.tmp"
        )
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self._state_path)


def main() -> None:
    """Serve the supervisor's bounded internal JSONL control channel."""
    role: QualificationRole | None = None
    for line in sys.stdin:
        request_id: object = None
        should_exit = False
        try:
            request = _mapping(json.loads(line), "role request")
            request_id = request.get("request_id")
            operation = _text(request, "operation")
            payload = _mapping(request.get("payload", {}), "payload")
            if role is None:
                if operation != "start":
                    raise RuntimeError("first role operation must be start")
                role = QualificationRole(payload)
                value = {
                    "role_id": role.role_id,
                    "process_id": os.getpid(),
                    "ready": True,
                }
            else:
                value = role.handle(operation, payload)
                should_exit = operation == "close"
            response = {
                "request_id": request_id,
                "ok": True,
                "value": value,
            }
        except Exception as error:
            response = {
                "request_id": request_id,
                "ok": False,
                "error": {
                    "type": type(error).__name__,
                    "message": str(error),
                },
            }
        sys.stdout.write(json.dumps(response, sort_keys=True) + "\n")
        sys.stdout.flush()
        if should_exit:
            return


def _identity(payload: Mapping[str, object]) -> NodeIdentity:
    return NodeIdentity(
        _text(payload, "cluster_id"),
        _text(payload, "node_id"),
        _text(payload, "instance_id"),
    )


def _cluster_config(value: Mapping[str, object]) -> ClusterConfig:
    members_value = value.get("members")
    if not isinstance(members_value, list):
        raise ValueError("coordinator config members must be a list")
    members = []
    for item in members_value:
        member = _mapping(item, "coordinator member")
        members.append(
            MemberConfig(
                _text(member, "node_id"),
                _text(member, "host"),
                _integer(member, "raft_port"),
                _integer(member, "api_port"),
            )
        )
    return ClusterConfig(tuple(members))


def _transport_config() -> TransportConfig:
    return TransportConfig(
        security=TransportSecurity.insecure_local_development(),
        outbound_queue_limit=64,
        inbound_queue_limit=64,
        max_payload_bytes=256 * 1024,
        connect_timeout=0.1,
        handshake_timeout=0.5,
        heartbeat_interval=0.05,
        peer_timeout=0.5,
        reconnect=ReconnectPolicy(0.02, 1.5, 0.1),
    )


def _lifecycle_event(event: MeshLifecycleEvent) -> dict[str, object]:
    return {
        "sequence": event.sequence,
        "kind": event.kind.value,
        "reason": event.reason.value,
        "node_id": event.node_id,
        "topic": event.topic,
        "peer_node_id": event.peer_node_id,
        "message_id": event.message_id,
        "correlation_id": event.correlation_id,
        "related_message_id": event.related_message_id,
        "attempt": event.attempt,
        "item_count": event.item_count,
        "byte_count": event.byte_count,
        "detail": event.detail,
    }


def _peer_health(peer: MeshPeerHealth) -> dict[str, object]:
    return {
        "node_id": peer.node_id,
        "source": peer.source,
        "link": {
            **asdict(peer.link),
            "state": peer.link.state.value,
            "local_identity": asdict(peer.link.local_identity),
            "remote_identity": (
                None
                if peer.link.remote_identity is None
                else asdict(peer.link.remote_identity)
            ),
        },
        "interested_topics": list(peer.interested_topics),
        "last_routing_error": peer.last_routing_error,
    }


def _semantic_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return sha256(encoded).hexdigest()


def _qualification_device(*, revision: int) -> WorldDevice:
    return WorldDevice(
        id=_WORLD_OWNER_ID,
        position=WorldPosition(float(revision), 0.0, 0.0),
        dimensions=WorldDimensions(0.256, 0.064, 0.01),
        capabilities=("pixel-sink",),
    )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object")
    return value


def _text(value: Mapping[str, object], name: str) -> str:
    item = value.get(name)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return item


def _integer(value: Mapping[str, object], name: str) -> int:
    item = value.get(name)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{name} must be an integer")
    return item


if __name__ == "__main__":
    main()
