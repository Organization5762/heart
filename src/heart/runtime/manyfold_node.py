from __future__ import annotations

import json
import os
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import final
from uuid import uuid4

from manyfold.architecture import (CompositeDiscovery, LinkState,
                                   MachineSignerClient, MembershipConfig,
                                   MeshConfig, MeshHealth, MeshPeerHealth,
                                   MeshPublication, MeshSubscription,
                                   NodeIdentity, PeerEndpoint, PubSub,
                                   PubSubCallbackSubscription, PubSubTopic,
                                   ReconnectPolicy, StaticSeedDiscovery,
                                   TcpAddress, TransportConfig, TransportMesh,
                                   TransportSecurity)
from manyfold.architecture.swim import (HmacDatagramTransport,
                                        HmacPeerCredentials,
                                        HmacTransportConfig, SwimConfig,
                                        SwimMessageTransport,
                                        UdpDatagramSocket)
from manyfold.architecture.transport_mesh import (MeshBackpressureError,
                                                  MeshClosed, MeshRouteError)
from manyfold.architecture.transport_mesh import \
    PeerDiscovery as MeshPeerDiscovery
from manyfold.cluster import (NodeConfig, NodeRuntime, NodeSnapshot,
                              ProcessTransportSecurity)

from heart.peripheral.core.input.events import (FRAME_TICK_TOPIC,
                                                INPUT_EVENT_TOPIC)
from heart.peripheral.core.input.external_sensors import (
    EXTERNAL_SENSOR_STATE_TOPIC, ExternalSensorStateEvent,
    external_sensor_state_topic)
from heart.peripheral.core.input.profiles.navigation import (
    HEART_INPUT_PUBSUB, NAVIGATION_TOPIC, NavigationEvent)
from heart.utilities.logging import get_logger

DEFAULT_MAX_PUBLICATIONS_PER_POLL = 64
DEFAULT_SENSOR_MESH_INTERVAL_SECONDS = 0.1
DEFAULT_SEEN_EVENT_LIMIT = 4096
HEART_MANYFOLD_CONFIG = "HEART_MANYFOLD_CONFIG"
HEART_MANYFOLD_PUBSUB = "heart"
HEART_MANYFOLD_STATUS_TOPIC = "heart.node.status"
MICROPHONE_SAMPLE_STREAM = "heart.microphone.level"
RENDERED_FRAME_STREAM = "heart.rendered_frame"

logger = get_logger(__name__)


def topic_policy_manifest() -> tuple[dict[str, object], ...]:
    """Return the authoritative machine-readable Heart distribution policy."""
    return tuple(asdict(policy) for policy in HEART_TOPIC_POLICIES)


@final
class TopicDelivery(str, Enum):
    """How one named Heart stream may leave its process."""

    LOCAL = "local"
    MESH_BEST_EFFORT = "mesh_best_effort"
    MESH_COALESCED = "mesh_coalesced"


@final
@dataclass(frozen=True, slots=True)
class TopicPolicy:
    """Explicit transport and persistence decision for one Heart stream."""

    topic: str
    delivery: TopicDelivery
    purpose: str
    durable: bool = False
    raft: bool = False


HEART_TOPIC_POLICIES = (
    TopicPolicy(
        HEART_MANYFOLD_STATUS_TOPIC,
        TopicDelivery.MESH_BEST_EFFORT,
        "node lifecycle and peer health",
    ),
    TopicPolicy(
        NAVIGATION_TOPIC,
        TopicDelivery.MESH_BEST_EFFORT,
        "deduplicated user navigation intent",
    ),
    TopicPolicy(
        EXTERNAL_SENSOR_STATE_TOPIC,
        TopicDelivery.MESH_COALESCED,
        "selected low-rate external sensor state",
    ),
    TopicPolicy(
        FRAME_TICK_TOPIC,
        TopicDelivery.LOCAL,
        "frame-clock scheduling",
    ),
    TopicPolicy(
        RENDERED_FRAME_STREAM,
        TopicDelivery.LOCAL,
        "rendered frame buffers",
    ),
    TopicPolicy(
        MICROPHONE_SAMPLE_STREAM,
        TopicDelivery.LOCAL,
        "microphone-rate samples",
    ),
    TopicPolicy(
        INPUT_EVENT_TOPIC,
        TopicDelivery.LOCAL,
        "input debug taps",
    ),
)


@final
@dataclass(frozen=True, slots=True)
class ManyfoldNodeConfig:
    """Optional canonical ManyFold node and mesh configuration."""

    bootstrap: _HeartNodeBootstrap | None

    @property
    def is_enabled(self) -> bool:
        return self.bootstrap is not None

    @classmethod
    def from_environment(cls) -> "ManyfoldNodeConfig":
        """Load an optional signer-enrolled node from ``HEART_MANYFOLD_CONFIG``."""
        value = os.environ.get(HEART_MANYFOLD_CONFIG, "").strip()
        if not value:
            return cls(bootstrap=None)
        return cls.from_file(Path(value).expanduser())

    @classmethod
    def from_file(cls, path: Path) -> "ManyfoldNodeConfig":
        """Load one strict JSON bootstrap file."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise ValueError(
                f"Failed to read ManyFold node config {path}: {error}"
            ) from error
        except json.JSONDecodeError as error:
            raise ValueError(
                f"ManyFold node config {path} must contain valid JSON: {error}"
            ) from error
        return cls(bootstrap=_bootstrap_from_json(_require_mapping(raw, "config")))


@final
@dataclass(frozen=True, slots=True)
class ManyfoldNodeStatus:
    """Heart-facing canonical node and mesh lifecycle snapshot."""

    is_enabled: bool
    is_started: bool
    node: NodeSnapshot | None
    mesh: MeshHealth | None
    mesh_peers: tuple[MeshPeerHealth, ...]


@final
@dataclass(frozen=True, slots=True)
class ManyfoldNodeEvent:
    """Compact distributed status row for operations and SQL inspection."""

    event_type: str
    event_id: str
    origin_node_id: str
    authenticated_peers_json: str
    members_json: str
    candidate_count: int
    discovery_failure_count: int
    last_error: str
    timestamp_monotonic: float


@final
class ManyfoldNodeRuntime:
    """Apply Heart topic policy beside ManyFold's canonical node bootstrap."""

    def __init__(self, config: ManyfoldNodeConfig | None = None) -> None:
        self.config = config or ManyfoldNodeConfig.from_environment()
        self.status_topic = PubSubTopic(
            HEART_MANYFOLD_STATUS_TOPIC,
            schema=ManyfoldNodeEvent,
            pubsub=HEART_MANYFOLD_PUBSUB,
        )
        self._node: NodeRuntime | None = None
        self._mesh: TransportMesh | None = None
        self._signer_client: MachineSignerClient | None = None
        self._mesh_subscriptions: list[MeshSubscription] = []
        self._local_subscriptions: list[PubSubCallbackSubscription] = []
        self._topics: dict[str, PubSub] = {}
        self._pending_sensor: ExternalSensorStateEvent | None = None
        self._pending_sensor_lock = Lock()
        self._next_sensor_publish_at = 0.0
        self._seen = _SeenEventIds(DEFAULT_SEEN_EVENT_LIMIT)
        self._last_status_key: tuple[object, ...] | None = None

    @property
    def is_started(self) -> bool:
        return self._node is not None

    def start(self) -> ManyfoldNodeStatus:
        """Start signer-backed bootstrap and the public best-effort mesh once."""
        if self._node is not None:
            return self.status()
        bootstrap = self.config.bootstrap
        if bootstrap is None:
            return self.status()
        signer_client = MachineSignerClient(
            bootstrap.signer_socket,
            bootstrap.identity,
        )
        security_provider = _MachineSignerSecurityProvider(
            signer_client,
            bootstrap.connector_server_hostname,
            bootstrap.transport,
        )
        node = NodeRuntime(bootstrap.node_config(security_provider))
        self._signer_client = signer_client
        self._node = node
        try:
            node.start()
            process_security = security_provider.process_security
            mesh = TransportMesh(
                bootstrap.identity,
                connector_config=process_security.connector_transport,
                listener_config=process_security.listener_transport,
                config=bootstrap.mesh,
            )
            self._mesh = mesh
            bootstrap.configure_mesh(mesh, process_security)
            self._install_bridges()
            self._publish_status("started")
        except Exception:
            self.close()
            raise
        return self.status()

    def status(self) -> ManyfoldNodeStatus:
        node = self._node
        mesh = self._mesh
        return ManyfoldNodeStatus(
            is_enabled=self.config.is_enabled,
            is_started=node is not None,
            node=None if node is None else node.snapshot(),
            mesh=None if mesh is None else mesh.health(),
            mesh_peers=() if mesh is None else mesh.peer_health(),
        )

    def poll(self) -> None:
        """Drain bounded mesh work without running discovery or SWIM inline."""
        node = self._node
        mesh = self._mesh
        if node is None or mesh is None:
            return
        self._flush_sensor()
        for _index in range(DEFAULT_MAX_PUBLICATIONS_PER_POLL):
            try:
                publication = mesh.receive(timeout=0.0)
            except TimeoutError:
                break
            except MeshClosed:
                return
            self._accept_publication(publication)
        snapshot = node.snapshot()
        peer_health = mesh.peer_health()
        status_key = _status_key(snapshot, peer_health)
        if status_key != self._last_status_key:
            self._publish_status(
                "changed",
                snapshot=snapshot,
                peer_health=peer_health,
            )

    def close(self) -> None:
        """Release bridges, mesh, canonical bootstrap, and signer client."""
        node = self._node
        mesh = self._mesh
        signer_client = self._signer_client
        if node is None and mesh is None and signer_client is None:
            return
        if node is not None and mesh is not None:
            self._publish_status("stopping")
        for local_subscription in reversed(self._local_subscriptions):
            local_subscription.dispose()
        self._local_subscriptions.clear()
        for mesh_subscription in reversed(self._mesh_subscriptions):
            try:
                mesh_subscription.dispose()
            except (MeshBackpressureError, MeshClosed) as error:
                logger.warning("ManyFold topic withdrawal failed: %s", error)
        self._mesh_subscriptions.clear()
        self._topics.clear()
        with self._pending_sensor_lock:
            self._pending_sensor = None
        self._mesh = None
        self._node = None
        self._signer_client = None
        try:
            if mesh is not None:
                mesh.close()
        finally:
            try:
                if node is not None:
                    node.stop()
            finally:
                if signer_client is not None:
                    signer_client.close()
        self._last_status_key = None

    def _install_bridges(self) -> None:
        mesh = self._require_mesh()
        navigation_topic = PubSubTopic(
            NAVIGATION_TOPIC,
            schema=NavigationEvent,
            pubsub=HEART_INPUT_PUBSUB,
        )
        sensor_topic = external_sensor_state_topic()
        self._topics = {
            HEART_MANYFOLD_STATUS_TOPIC: self.status_topic,
            NAVIGATION_TOPIC: navigation_topic,
            EXTERNAL_SENSOR_STATE_TOPIC: sensor_topic,
        }
        self._mesh_subscriptions = [mesh.subscribe(topic) for topic in self._topics]
        self._local_subscriptions = [
            self.status_topic.subscribe(self._publish_local_status),
            navigation_topic.subscribe(self._publish_local_navigation),
            sensor_topic.subscribe(self._queue_local_sensor),
        ]

    def _publish_local_status(self, event: ManyfoldNodeEvent) -> None:
        if event.event_id:
            return
        self._publish_mesh(
            HEART_MANYFOLD_STATUS_TOPIC,
            {
                "event_type": event.event_type,
                "origin_node_id": event.origin_node_id,
                "authenticated_peers_json": event.authenticated_peers_json,
                "members_json": event.members_json,
                "candidate_count": event.candidate_count,
                "discovery_failure_count": event.discovery_failure_count,
                "last_error": event.last_error,
                "timestamp_monotonic": event.timestamp_monotonic,
            },
        )

    def _publish_local_navigation(self, event: NavigationEvent) -> None:
        if event.event_id:
            return
        self._publish_mesh(
            NAVIGATION_TOPIC,
            {
                "kind": event.kind,
                "source": event.source,
                "step": event.step,
            },
        )

    def _queue_local_sensor(self, event: ExternalSensorStateEvent) -> None:
        if event.event_id:
            return
        with self._pending_sensor_lock:
            self._pending_sensor = event

    def _flush_sensor(self) -> None:
        now = time.monotonic()
        if now < self._next_sensor_publish_at:
            return
        with self._pending_sensor_lock:
            event = self._pending_sensor
            self._pending_sensor = None
        if event is None:
            return
        self._next_sensor_publish_at = now + DEFAULT_SENSOR_MESH_INTERVAL_SECONDS
        self._publish_mesh(
            EXTERNAL_SENSOR_STATE_TOPIC,
            {
                "sensor_key": event.sensor_key,
                "value": event.value,
            },
        )

    def _publish_mesh(self, topic: str, payload: Mapping[str, object]) -> None:
        node = self._require_node()
        mesh = self._require_mesh()
        event_id = f"{node.config.identity.node_id}:{uuid4().hex}"
        encoded = json.dumps(
            {"event_id": event_id, "payload": payload},
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        try:
            mesh.publish(topic, encoded, message_id=event_id)
        except (MeshBackpressureError, MeshClosed, MeshRouteError) as error:
            logger.warning("ManyFold best-effort topic %s dropped: %s", topic, error)
            return
        self._seen.add(event_id)

    def _accept_publication(self, publication: MeshPublication) -> None:
        node = self._require_node()
        if publication.source_node_id == node.config.identity.node_id:
            return
        try:
            event_id, payload = _decode_mesh_payload(publication.payload)
            if event_id != publication.message_id:
                raise ValueError("event_id does not match mesh message_id")
        except ValueError as error:
            logger.warning(
                "Ignoring malformed ManyFold topic %s from %s: %s",
                publication.topic,
                publication.source_node_id,
                error,
            )
            return
        if self._seen.contains(event_id):
            return
        self._seen.add(event_id)
        topic = self._topics.get(publication.topic)
        if topic is None:
            return
        if publication.topic == NAVIGATION_TOPIC:
            topic.publish(
                NavigationEvent(
                    kind=_require_text(payload.get("kind"), "navigation kind"),
                    source=_require_text(payload.get("source"), "navigation source"),
                    step=_require_integer(payload.get("step"), "navigation step"),
                    event_id=event_id,
                    origin_node_id=publication.source_node_id,
                )
            )
        elif publication.topic == EXTERNAL_SENSOR_STATE_TOPIC:
            topic.publish(
                ExternalSensorStateEvent(
                    sensor_key=_require_text(payload.get("sensor_key"), "sensor key"),
                    value=_optional_number(payload.get("value"), "sensor value"),
                    event_id=event_id,
                    origin_node_id=publication.source_node_id,
                )
            )
        else:
            topic.publish(
                ManyfoldNodeEvent(
                    event_type=_require_text(payload.get("event_type"), "event type"),
                    event_id=event_id,
                    origin_node_id=publication.source_node_id,
                    authenticated_peers_json=_require_text(
                        payload.get("authenticated_peers_json"),
                        "authenticated peers",
                    ),
                    members_json=_require_text(payload.get("members_json"), "members"),
                    candidate_count=_require_integer(
                        payload.get("candidate_count"),
                        "candidate count",
                    ),
                    discovery_failure_count=_require_integer(
                        payload.get("discovery_failure_count"),
                        "discovery failure count",
                    ),
                    last_error=_require_string(payload.get("last_error"), "last error"),
                    timestamp_monotonic=_require_number(
                        payload.get("timestamp_monotonic"),
                        "status timestamp",
                    ),
                )
            )

    def _publish_status(
        self,
        event_type: str,
        *,
        snapshot: NodeSnapshot | None = None,
        peer_health: tuple[MeshPeerHealth, ...] | None = None,
    ) -> None:
        node = self._require_node()
        mesh = self._require_mesh()
        resolved_snapshot = snapshot or node.snapshot()
        resolved_peer_health = peer_health or mesh.peer_health()
        self._last_status_key = _status_key(
            resolved_snapshot,
            resolved_peer_health,
        )
        authenticated_peers = sorted(
            {
                peer.health.remote_identity.node_id
                for peer in resolved_snapshot.peers
                if peer.health.state is LinkState.CONNECTED
                and peer.health.remote_identity is not None
            }
        )
        self.status_topic.publish(
            ManyfoldNodeEvent(
                event_type=event_type,
                event_id="",
                origin_node_id=resolved_snapshot.identity.node_id,
                authenticated_peers_json=json.dumps(authenticated_peers),
                members_json=json.dumps(
                    [
                        {
                            "node_id": member.identity.node_id,
                            "instance_id": member.identity.instance_id,
                            "incarnation": member.incarnation,
                            "state": member.state.value,
                        }
                        for member in resolved_snapshot.members
                    ],
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                candidate_count=len(resolved_snapshot.peers),
                discovery_failure_count=sum(
                    diagnostic.code.startswith("discovery-")
                    and diagnostic.severity.value != "info"
                    for diagnostic in resolved_snapshot.diagnostics
                ),
                last_error=_last_node_error(resolved_snapshot),
                timestamp_monotonic=time.monotonic(),
            )
        )

    def _require_node(self) -> NodeRuntime:
        if self._node is None:
            raise RuntimeError("Heart ManyFold node is not started")
        return self._node

    def _require_mesh(self) -> TransportMesh:
        if self._mesh is None:
            raise RuntimeError("Heart ManyFold mesh is not started")
        return self._mesh


@final
@dataclass(frozen=True, slots=True)
class _TransportLimits:
    outbound_queue_limit: int
    inbound_queue_limit: int
    max_payload_bytes: int
    connect_timeout: float
    handshake_timeout: float
    heartbeat_interval: float
    peer_timeout: float
    reconnect: ReconnectPolicy

    def config(self, security: TransportSecurity) -> TransportConfig:
        return TransportConfig(
            security=security,
            outbound_queue_limit=self.outbound_queue_limit,
            inbound_queue_limit=self.inbound_queue_limit,
            max_payload_bytes=self.max_payload_bytes,
            connect_timeout=self.connect_timeout,
            handshake_timeout=self.handshake_timeout,
            heartbeat_interval=self.heartbeat_interval,
            peer_timeout=self.peer_timeout,
            reconnect=self.reconnect,
        )


@final
@dataclass(frozen=True, slots=True)
class _MeshPeer:
    node_id: str
    bootstrap_endpoint: PeerEndpoint
    mesh_address: TcpAddress
    swim_key: bytes
    mesh_role: str
    mesh_listen_address: TcpAddress | None


@final
@dataclass(frozen=True, slots=True)
class _HeartNodeBootstrap:
    identity: NodeIdentity
    listen_address: TcpAddress
    signer_socket: Path
    connector_server_hostname: str
    local_swim_key: bytes
    peers: tuple[_MeshPeer, ...]
    local_incarnation: int
    transport: _TransportLimits
    membership: MembershipConfig
    swim: SwimConfig
    swim_transport: HmacTransportConfig
    mesh: MeshConfig
    reconcile_interval_seconds: float
    startup_peer_timeout_seconds: float
    peer_absence_seconds: float
    signer_timeout_seconds: float
    minimum_credential_lifetime_seconds: float
    shutdown_timeout_seconds: float

    def node_config(
        self,
        security_provider: _MachineSignerSecurityProvider,
    ) -> NodeConfig:
        endpoints = tuple(peer.bootstrap_endpoint for peer in self.peers)
        max_peers = max(1, len(self.peers))
        return NodeConfig(
            identity=self.identity,
            listen_address=self.listen_address,
            discovery=CompositeDiscovery(
                (
                    StaticSeedDiscovery(
                        endpoints,
                        max_candidates=max_peers,
                    ),
                ),
                max_candidates=max_peers,
            ),
            transport_security_provider=security_provider,
            membership=self.membership,
            swim=self.swim,
            swim_transport_factory=self._swim_transport,
            local_incarnation=self.local_incarnation,
            max_peers=max_peers,
            reconcile_interval_seconds=self.reconcile_interval_seconds,
            startup_peer_timeout_seconds=self.startup_peer_timeout_seconds,
            peer_absence_seconds=self.peer_absence_seconds,
            signer_timeout_seconds=self.signer_timeout_seconds,
            minimum_credential_lifetime_seconds=(
                self.minimum_credential_lifetime_seconds
            ),
            shutdown_timeout_seconds=self.shutdown_timeout_seconds,
        )

    def configure_mesh(
        self,
        mesh: TransportMesh,
        security: ProcessTransportSecurity,
    ) -> None:
        for peer in self.peers:
            if peer.mesh_role == "listen":
                mesh.listen(
                    peer.node_id,
                    peer.mesh_listen_address,
                    transport_config=security.listener_transport,
                )
        mesh.apply_discovery(
            tuple(
                MeshPeerDiscovery(
                    peer.node_id,
                    peer.mesh_address,
                    transport_config=security.connector_transport,
                )
                for peer in self.peers
                if peer.mesh_role == "connect"
            )
        )

    def _swim_transport(
        self,
        identity: NodeIdentity,
        endpoint: PeerEndpoint,
    ) -> SwimMessageTransport:
        return HmacDatagramTransport(
            UdpDatagramSocket(endpoint),
            HmacPeerCredentials(
                local_identity=identity,
                advertised_endpoint=endpoint,
                local_key=self.local_swim_key,
                peer_keys={peer.node_id: peer.swim_key for peer in self.peers},
                max_peers=max(1, len(self.peers)),
            ),
            config=self.swim_transport,
        )


@final
class _MachineSignerSecurityProvider:
    def __init__(
        self,
        client: MachineSignerClient,
        server_hostname: str,
        limits: _TransportLimits,
    ) -> None:
        self._client = client
        self._server_hostname = server_hostname
        self._limits = limits
        self._process_security: ProcessTransportSecurity | None = None

    @property
    def process_security(self) -> ProcessTransportSecurity:
        if self._process_security is None:
            raise RuntimeError(
                "canonical node bootstrap did not acquire signer security"
            )
        return self._process_security

    def acquire(
        self,
        identity: NodeIdentity,
        *,
        timeout_seconds: float,
        minimum_lifetime_seconds: float,
    ) -> ProcessTransportSecurity:
        if identity != self._client.identity:
            raise ValueError("signer client identity does not match node identity")
        status = self._client.ensure_process_credentials(
            max_attempts=3,
            retry_delay_seconds=min(0.05, timeout_seconds / 3),
        )
        if not status.is_usable or status.expires_at is None:
            raise RuntimeError("machine signer returned no usable process credential")
        remaining_seconds = status.expires_at.timestamp() - time.time()
        if remaining_seconds < minimum_lifetime_seconds:
            raise RuntimeError(
                "machine signer credential lifetime is insufficient: "
                f"remaining={max(0.0, remaining_seconds):.3f}s "
                f"required={minimum_lifetime_seconds:.3f}s"
            )
        process_security = ProcessTransportSecurity(
            listener_transport=self._limits.config(
                self._client.transport_security(server_side=True)
            ),
            connector_transport=self._limits.config(
                self._client.transport_security(
                    server_side=False,
                    server_hostname=self._server_hostname,
                )
            ),
            expires_at_epoch_seconds=status.expires_at.timestamp(),
        )
        self._process_security = process_security
        return process_security


def _bootstrap_from_json(raw: Mapping[str, object]) -> _HeartNodeBootstrap:
    identity = NodeIdentity(
        _mapping_text(raw, "cluster_id"),
        _mapping_text(raw, "node_id"),
        _mapping_text(raw, "instance_id"),
    )
    peers = tuple(
        _mesh_peer_from_json(_require_mapping(peer, "peer"))
        for peer in _require_list(raw.get("peers"), "peers")
    )
    max_peers = max(1, len(peers))
    return _HeartNodeBootstrap(
        identity=identity,
        listen_address=TcpAddress(
            _mapping_text(raw, "listen_host"),
            _mapping_integer(raw, "listen_port"),
        ),
        signer_socket=Path(_mapping_text(raw, "signer_socket")).expanduser(),
        connector_server_hostname=_mapping_text(
            raw,
            "connector_server_hostname",
        ),
        local_swim_key=_mapping_hex_bytes(raw, "swim_key_hex"),
        peers=peers,
        local_incarnation=_mapping_integer(raw, "incarnation", default=0),
        transport=_transport_limits_from_json(raw),
        membership=MembershipConfig(
            lease_seconds=_mapping_number(raw, "lease_seconds", default=15.0),
            suspect_seconds=_mapping_number(raw, "suspect_seconds", default=5.0),
            dead_retention_seconds=_mapping_number(
                raw,
                "dead_retention_seconds",
                default=300.0,
            ),
            max_members=_mapping_integer(
                raw,
                "max_members",
                default=max_peers + 1,
            ),
            max_changes=_mapping_integer(raw, "max_membership_changes", default=256),
        ),
        swim=SwimConfig(
            probe_interval_seconds=_mapping_number(
                raw,
                "swim_probe_interval_seconds",
                default=1.0,
            ),
            ping_timeout_seconds=_mapping_number(
                raw,
                "swim_ping_timeout_seconds",
                default=0.2,
            ),
            indirect_timeout_seconds=_mapping_number(
                raw,
                "swim_indirect_timeout_seconds",
                default=0.3,
            ),
            helper_count=_mapping_integer(raw, "swim_helper_count", default=3),
        ),
        swim_transport=HmacTransportConfig(),
        mesh=MeshConfig(
            max_peers=_mapping_integer(raw, "max_mesh_peers", default=32),
            max_subscriptions=_mapping_integer(
                raw,
                "max_mesh_subscriptions",
                default=4096,
            ),
            duplicate_window=_mapping_integer(
                raw,
                "mesh_duplicate_window",
                default=8192,
            ),
            publication_queue_limit=_mapping_integer(
                raw,
                "mesh_publication_queue_limit",
                default=1024,
            ),
        ),
        reconcile_interval_seconds=_mapping_number(
            raw,
            "reconcile_interval_seconds",
            default=0.1,
        ),
        startup_peer_timeout_seconds=_mapping_number(
            raw,
            "startup_peer_timeout_seconds",
            default=0.1,
        ),
        peer_absence_seconds=_mapping_number(
            raw,
            "peer_absence_seconds",
            default=15.0,
        ),
        signer_timeout_seconds=_mapping_number(
            raw,
            "signer_timeout_seconds",
            default=2.0,
        ),
        minimum_credential_lifetime_seconds=_mapping_number(
            raw,
            "minimum_credential_lifetime_seconds",
            default=30.0,
        ),
        shutdown_timeout_seconds=_mapping_number(
            raw,
            "shutdown_timeout_seconds",
            default=5.0,
        ),
    )


def _mesh_peer_from_json(raw: Mapping[str, object]) -> _MeshPeer:
    mesh_role = _mapping_text(raw, "mesh_role")
    if mesh_role not in {"connect", "listen"}:
        raise ValueError("mesh_role must be 'connect' or 'listen'")
    listen_address = None
    if mesh_role == "listen":
        listen_address = TcpAddress(
            _mapping_text(raw, "mesh_listen_host"),
            _mapping_integer(raw, "mesh_listen_port"),
        )
    return _MeshPeer(
        node_id=_mapping_text(raw, "node_id"),
        bootstrap_endpoint=PeerEndpoint(
            _mapping_text(raw, "bootstrap_host"),
            _mapping_integer(raw, "bootstrap_port"),
        ),
        mesh_address=TcpAddress(
            _mapping_text(raw, "mesh_host"),
            _mapping_integer(raw, "mesh_port"),
        ),
        swim_key=_mapping_hex_bytes(raw, "swim_key_hex"),
        mesh_role=mesh_role,
        mesh_listen_address=listen_address,
    )


def _transport_limits_from_json(raw: Mapping[str, object]) -> _TransportLimits:
    return _TransportLimits(
        outbound_queue_limit=_mapping_integer(
            raw,
            "transport_outbound_queue_limit",
            default=1024,
        ),
        inbound_queue_limit=_mapping_integer(
            raw,
            "transport_inbound_queue_limit",
            default=1024,
        ),
        max_payload_bytes=_mapping_integer(
            raw,
            "transport_max_payload_bytes",
            default=16 * 1024 * 1024,
        ),
        connect_timeout=_mapping_number(
            raw,
            "transport_connect_timeout_seconds",
            default=2.0,
        ),
        handshake_timeout=_mapping_number(
            raw,
            "transport_handshake_timeout_seconds",
            default=2.0,
        ),
        heartbeat_interval=_mapping_number(
            raw,
            "transport_heartbeat_interval_seconds",
            default=1.0,
        ),
        peer_timeout=_mapping_number(
            raw,
            "transport_peer_timeout_seconds",
            default=5.0,
        ),
        reconnect=ReconnectPolicy(
            initial_delay=_mapping_number(
                raw,
                "transport_reconnect_initial_seconds",
                default=0.05,
            ),
            multiplier=_mapping_number(
                raw,
                "transport_reconnect_multiplier",
                default=2.0,
            ),
            max_delay=_mapping_number(
                raw,
                "transport_reconnect_max_seconds",
                default=1.0,
            ),
        ),
    )


def _decode_mesh_payload(payload: bytes) -> tuple[str, Mapping[str, object]]:
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"payload must be UTF-8 JSON: {error}") from error
    envelope = _require_mapping(raw, "mesh envelope")
    event_id = _mapping_text(envelope, "event_id")
    return event_id, _require_mapping(envelope.get("payload"), "mesh payload")


def _status_key(
    snapshot: NodeSnapshot,
    mesh_peers: tuple[MeshPeerHealth, ...],
) -> tuple[object, ...]:
    return (
        snapshot.phase.value,
        tuple(
            (
                member.identity.node_id,
                member.identity.instance_id,
                member.incarnation,
                member.state.value,
            )
            for member in snapshot.members
        ),
        tuple(
            (
                peer.endpoint.host,
                peer.endpoint.port,
                peer.health.state.value,
                (
                    ""
                    if peer.health.remote_identity is None
                    else peer.health.remote_identity.instance_id
                ),
            )
            for peer in snapshot.peers
        ),
        tuple(
            (
                peer.node_id,
                peer.link.state.value,
                tuple(peer.interested_topics),
            )
            for peer in mesh_peers
        ),
        tuple(
            (diagnostic.sequence, diagnostic.code)
            for diagnostic in snapshot.diagnostics
        ),
    )


def _last_node_error(snapshot: NodeSnapshot) -> str:
    for diagnostic in reversed(snapshot.diagnostics):
        if diagnostic.severity.value == "error":
            return diagnostic.message
    return ""


def _mapping_hex_bytes(raw: Mapping[str, object], name: str) -> bytes:
    value = _mapping_text(raw, name)
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{name} must be hexadecimal bytes") from error


def _mapping_integer(
    raw: Mapping[str, object],
    name: str,
    *,
    default: int | None = None,
) -> int:
    if name not in raw:
        if default is None:
            raise ValueError(f"{name} is required")
        return default
    return _require_integer(raw[name], name)


def _mapping_number(
    raw: Mapping[str, object],
    name: str,
    *,
    default: float,
) -> float:
    if name not in raw:
        return default
    return _require_number(raw[name], name)


def _mapping_text(raw: Mapping[str, object], name: str) -> str:
    if name not in raw:
        raise ValueError(f"{name} is required")
    return _require_text(raw[name], name)


def _optional_number(value: object, name: str) -> float | None:
    if value is None:
        return None
    return _require_number(value, name)


def _require_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _require_list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def _require_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object with string keys")
    return value


def _require_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a number")
    return float(value)


def _require_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    return value


def _require_text(value: object, name: str) -> str:
    result = _require_string(value, name).strip()
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


@final
class _SeenEventIds:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._order: deque[str] = deque()
        self._ids: set[str] = set()
        self._lock = Lock()

    def add(self, event_id: str) -> None:
        with self._lock:
            if event_id in self._ids:
                return
            while len(self._order) >= self._limit:
                expired = self._order.popleft()
                self._ids.remove(expired)
            self._order.append(event_id)
            self._ids.add(event_id)

    def contains(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._ids
