from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import final

from manyfold.architecture import (CompositeDiscovery, DurableTopicDiagnostics,
                                   MachineSignerClient, MembershipConfig,
                                   MeshConfig, MeshDurabilityConfig,
                                   MeshHealth, MeshLifecycleEvent,
                                   MeshLifecycleHealth, MeshLifecycleKind,
                                   MeshLifecycleSubscription, MeshPeerHealth,
                                   MeshTopicBinding, MeshTopicPolicy,
                                   NodeIdentity, PeerEndpoint, PubSub,
                                   ReconnectPolicy, StaticSeedDiscovery,
                                   TcpAddress, TransportConfig, TransportMesh,
                                   TransportSecurity)
from manyfold.architecture.swim import (HmacDatagramTransport,
                                        HmacPeerCredentials,
                                        HmacTransportConfig, SwimConfig,
                                        SwimMessageTransport,
                                        UdpDatagramSocket)
from manyfold.architecture.transport_mesh import \
    PeerDiscovery as MeshPeerDiscovery
from manyfold.cluster import (NodeConfig, NodeRuntime, NodeSnapshot,
                              ProcessTransportSecurity)

from heart.peripheral.core.input.events import (FRAME_TICK_TOPIC,
                                                INPUT_EVENT_TOPIC,
                                                frame_tick_topic,
                                                input_event_topic)
from heart.peripheral.core.input.external_sensors import (
    EXTERNAL_SENSOR_STATE_TOPIC, external_sensor_state_topic)
from heart.peripheral.core.input.frame import FrameTick
from heart.peripheral.core.input.profiles.navigation import (NAVIGATION_TOPIC,
                                                             navigation_topic)
from heart.peripheral.led_matrix import (HEART_RENDERED_FRAME_TOPIC,
                                         rendered_frame_topic)
from heart.peripheral.microphone import (HEART_MICROPHONE_SAMPLE_TOPIC,
                                         microphone_sample_topic)
from heart.runtime.domain_lifecycle import (INPUT_LIFECYCLE_TOPIC,
                                            PERIPHERAL_LIFECYCLE_TOPIC,
                                            PIPELINE_LIFECYCLE_TOPIC,
                                            RENDERER_LIFECYCLE_TOPIC,
                                            SCENE_LIFECYCLE_TOPIC,
                                            SENSOR_LIFECYCLE_TOPIC,
                                            domain_lifecycle_topics)
from heart.utilities.logging import get_logger

HEART_MANYFOLD_CONFIG = "HEART_MANYFOLD_CONFIG"

logger = get_logger(__name__)


def topic_policy_manifest() -> tuple[dict[str, object], ...]:
    """Return the authoritative machine-readable Heart mesh contracts."""
    return tuple(contract.manifest() for contract in HEART_TOPIC_POLICIES)


def heart_topic_handles() -> tuple[PubSub, ...]:
    """Return the exact named PubSub handles used by Heart mesh processes."""
    return (
        navigation_topic(),
        external_sensor_state_topic(),
        frame_tick_topic(FrameTick),
        rendered_frame_topic(),
        microphone_sample_topic(),
        input_event_topic(),
        *domain_lifecycle_topics(),
    )


def bind_heart_topics(mesh: TransportMesh) -> tuple[MeshTopicBinding, ...]:
    """Bind every Heart topic before the mesh registers any peers."""
    topics = heart_topic_handles()
    contracts = {contract.topic: contract for contract in HEART_TOPIC_POLICIES}
    if {topic.topic for topic in topics} != set(contracts):
        raise RuntimeError("Heart topic handles do not match the declared contracts")
    return tuple(
        mesh.bind(topic, policy=contracts[topic.topic].policy) for topic in topics
    )


@final
@dataclass(frozen=True, slots=True)
class TopicPolicy:
    """Heart's application contract for one public ManyFold topic binding."""

    data_class: str
    policy: MeshTopicPolicy
    coalescing_key: str
    purpose: str
    raft: bool = False

    @property
    def topic(self) -> str:
        return self.policy.topic

    def manifest(self) -> dict[str, object]:
        journal = self.policy.journal_policy
        delivery_class = self.policy.delivery_class.value
        if delivery_class == "live_latest":
            delivery_class = "volatile_latest"
        return {
            "topic": self.topic,
            "data_class": self.data_class,
            "delivery_class": delivery_class,
            "coalescing_key": self.coalescing_key,
            "ttl_ms": (
                None if journal is None else round(journal.ttl_seconds * 1000)
            ),
            "max_items": self.policy.max_sources,
            "max_bytes": None if journal is None else journal.max_bytes,
            "max_message_bytes": self.policy.max_message_bytes,
            "raft": self.raft,
        }


HEART_TOPIC_POLICIES = (
    TopicPolicy(
        "NavigationEvent",
        MeshTopicPolicy.commands(
            NAVIGATION_TOPIC,
            max_items=256,
            max_bytes=1024 * 1024,
            max_message_bytes=16 * 1024,
            ttl_seconds=10.0,
        ),
        "request_id",
        "deduplicated user navigation intent",
    ),
    TopicPolicy(
        "ExternalSensorStateEvent",
        MeshTopicPolicy.latest(
            EXTERNAL_SENSOR_STATE_TOPIC,
            max_sources=128,
            max_bytes=2 * 1024 * 1024,
            max_message_bytes=32 * 1024,
            ttl_seconds=2.0,
            key_field="sensor_key",
        ),
        "origin_node_id + topic + sensor_key",
        "low-rate external sensor state with expiry",
    ),
    TopicPolicy(
        "FrameTick",
        MeshTopicPolicy.live_latest(
            FRAME_TICK_TOPIC,
            max_sources=1,
            max_message_bytes=1024,
        ),
        "origin_node_id + topic",
        "current frame-clock state",
    ),
    TopicPolicy(
        "SensorEvent[DisplayFrame]",
        MeshTopicPolicy.live_latest(
            HEART_RENDERED_FRAME_TOPIC,
            max_sources=8,
            max_message_bytes=128 * 1024,
        ),
        "origin_node_id + topic + display identity",
        "current rendered frame projection",
    ),
    TopicPolicy(
        "SensorEvent[MicrophoneLevel]",
        MeshTopicPolicy.live_latest(
            HEART_MICROPHONE_SAMPLE_TOPIC,
            max_sources=8,
            max_message_bytes=4 * 1024,
        ),
        "origin_node_id + topic + microphone identity",
        "current microphone level projection",
    ),
    TopicPolicy(
        "InputEvent",
        MeshTopicPolicy.live_latest(
            INPUT_EVENT_TOPIC,
            max_sources=128,
            max_message_bytes=16 * 1024,
        ),
        "origin_node_id + topic + stage + stream_name + source_id",
        "bounded current debug and input projections",
    ),
    TopicPolicy(
        "HeartDomainTransition",
        MeshTopicPolicy.commands(
            PERIPHERAL_LIFECYCLE_TOPIC,
            max_items=256,
            max_bytes=1024 * 1024,
            max_message_bytes=4096,
            ttl_seconds=30.0,
        ),
        "event_id",
        "peripheral attachment transitions",
    ),
    TopicPolicy(
        "HeartDomainTransition",
        MeshTopicPolicy.commands(
            INPUT_LIFECYCLE_TOPIC,
            max_items=256,
            max_bytes=1024 * 1024,
            max_message_bytes=4096,
            ttl_seconds=30.0,
        ),
        "event_id",
        "input source availability transitions",
    ),
    TopicPolicy(
        "HeartDomainTransition",
        MeshTopicPolicy.commands(
            SCENE_LIFECYCLE_TOPIC,
            max_items=256,
            max_bytes=1024 * 1024,
            max_message_bytes=4096,
            ttl_seconds=30.0,
        ),
        "event_id",
        "scene selection and activation transitions",
    ),
    TopicPolicy(
        "HeartDomainTransition",
        MeshTopicPolicy.commands(
            RENDERER_LIFECYCLE_TOPIC,
            max_items=256,
            max_bytes=1024 * 1024,
            max_message_bytes=4096,
            ttl_seconds=30.0,
        ),
        "event_id",
        "renderer worker transitions",
    ),
    TopicPolicy(
        "HeartDomainTransition",
        MeshTopicPolicy.commands(
            SENSOR_LIFECYCLE_TOPIC,
            max_items=256,
            max_bytes=1024 * 1024,
            max_message_bytes=4096,
            ttl_seconds=30.0,
        ),
        "event_id",
        "sensor availability transitions",
    ),
    TopicPolicy(
        "HeartDomainTransition",
        MeshTopicPolicy.commands(
            PIPELINE_LIFECYCLE_TOPIC,
            max_items=256,
            max_bytes=1024 * 1024,
            max_message_bytes=4096,
            ttl_seconds=30.0,
        ),
        "event_id",
        "coalesced frame and audio pressure transitions",
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
        """Load an optional signer-enrolled node from
        ``HEART_MANYFOLD_CONFIG``."""
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
    """Public ManyFold node, mesh, lifecycle, and topic health."""

    is_enabled: bool
    is_started: bool
    node: NodeSnapshot | None
    mesh: MeshHealth | None
    mesh_peers: tuple[MeshPeerHealth, ...]
    lifecycle: MeshLifecycleHealth | None
    topics: tuple[DurableTopicDiagnostics, ...]


@final
class ManyfoldNodeRuntime:
    """Bind Heart's named PubSub topics to one canonical ManyFold mesh."""

    def __init__(self, config: ManyfoldNodeConfig | None = None) -> None:
        self.config = config or ManyfoldNodeConfig.from_environment()
        self._node: NodeRuntime | None = None
        self._mesh: TransportMesh | None = None
        self._signer_client: MachineSignerClient | None = None
        self._bindings: list[MeshTopicBinding] = []
        self._topics: dict[str, PubSub] = {}
        self._lifecycle_after_sequence = 0

    @property
    def is_started(self) -> bool:
        return self._node is not None

    def start(self) -> ManyfoldNodeStatus:
        """Start signer-backed bootstrap and install direct topic bindings
        once."""
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
                durability=bootstrap.durability,
            )
            self._mesh = mesh
            self._install_bindings()
            bootstrap.configure_mesh(mesh, process_security)
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
            lifecycle=None if mesh is None else mesh.lifecycle_health(),
            topics=() if mesh is None else mesh.durable_topic_diagnostics(),
        )

    def poll(self) -> None:
        """Consume bounded public lifecycle transitions without transport
        polling."""
        mesh = self._mesh
        if mesh is None:
            return
        for event in mesh.lifecycle_events(
            after_sequence=self._lifecycle_after_sequence
        ):
            self._lifecycle_after_sequence = event.sequence
            if event.kind is MeshLifecycleKind.DELIVERY_FAILED:
                logger.warning(
                    "ManyFold delivery failed topic=%s peer=%s correlation=%s "
                    "reason=%s detail=%s",
                    event.topic,
                    event.peer_node_id,
                    event.correlation_id,
                    event.reason.value,
                    event.detail,
                )

    def lifecycle_events(
        self,
        *,
        after_sequence: int = 0,
    ) -> tuple[MeshLifecycleEvent, ...]:
        """Return typed ManyFold lifecycle events after a local sequence."""
        mesh = self._require_mesh()
        return mesh.lifecycle_events(after_sequence=after_sequence)

    def subscribe_lifecycle(
        self,
        *,
        after_sequence: int = 0,
        queue_limit: int = 1024,
    ) -> MeshLifecycleSubscription:
        """Return a bounded pull subscription to ManyFold lifecycle events."""
        return self._require_mesh().subscribe_lifecycle(
            after_sequence=after_sequence,
            queue_limit=queue_limit,
        )

    def lifecycle_health(self) -> MeshLifecycleHealth:
        """Return lifecycle retention and subscriber-drop health."""
        return self._require_mesh().lifecycle_health()

    def topic_diagnostics(self) -> tuple[DurableTopicDiagnostics, ...]:
        """Return public per-topic delivery and retention diagnostics."""
        return self._require_mesh().durable_topic_diagnostics()

    def close(self) -> None:
        """Release the mesh, canonical bootstrap, and signer client."""
        node = self._node
        mesh = self._mesh
        signer_client = self._signer_client
        if node is None and mesh is None and signer_client is None:
            return
        self._bindings.clear()
        self._topics.clear()
        self._mesh = None
        self._node = None
        self._signer_client = None
        self._lifecycle_after_sequence = 0
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

    def _install_bindings(self) -> None:
        self._bindings = list(bind_heart_topics(self._require_mesh()))
        self._topics = {
            binding.topic.topic: binding.topic for binding in self._bindings
        }

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
    durability: MeshDurabilityConfig
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
        durability=MeshDurabilityConfig(
            Path(_mapping_text(raw, "state_directory")).expanduser() / "delivery",
            hard_peer_items=_mapping_integer(
                raw,
                "durable_hard_peer_items",
                default=1024,
            ),
            hard_peer_bytes=_mapping_integer(
                raw,
                "durable_hard_peer_bytes",
                default=64 * 1024 * 1024,
            ),
            dedupe_retention_seconds=_mapping_number(
                raw,
                "durable_dedupe_retention_seconds",
                default=30.0,
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
