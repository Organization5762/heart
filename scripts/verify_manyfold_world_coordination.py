"""Prove Heart world coordination across Raft, RPC, and durable delivery."""

from __future__ import annotations

import argparse
import json
import tempfile
from importlib.metadata import distribution
from pathlib import Path
from typing import final

from manyfold.architecture.transport import (
    NodeIdentity,
    ReconnectPolicy,
    TcpTransport,
    TransportConfig,
    TransportSecurity,
)
from manyfold.architecture.transport_delivery import (
    DeliveryConfig,
    DurableDelivery,
)
from manyfold.architecture.transport_rpc import RpcEndpoint
from manyfold.cluster import CommittedCommand, ControlCommand, DevelopmentCluster

from heart.world import (
    COORDINATED_COMMAND_KINDS,
    EXCLUDED_DURABLE_DATA_KINDS,
    MODE_DELIVERY_CHANNEL,
    ActiveMode,
    WorldDevice,
    WorldDeviceRead,
    WorldDimensions,
    WorldPosition,
    WorldRpcClient,
    WorldRpcServer,
    WorldState,
    apply_delivered_mode,
    mode_delivery_message,
    put_device_command,
    select_mode_command,
)

_ARTIFACT_SCHEMA_VERSION = 1


def run_proof(root: Path) -> dict[str, object]:
    """Run the complete local fault story and return its JSON artifact."""
    root.mkdir(parents=True, exist_ok=True)
    cluster = DevelopmentCluster.create(root / "raft", node_count=3)
    device = _device()
    active_mode = _active_mode()
    device_command = put_device_command("heart-device-totem3-v1", device)
    mode_command = select_mode_command("heart-mode-mandelbulb-v1", active_mode)

    with cluster:
        node_ids = tuple(member.node_id for member in cluster.members)
        initial_process_ids = {
            node_id: cluster.process_id(node_id) for node_id in node_ids
        }
        initial_leader = cluster.wait_for_leader()
        device_commit = _commit(cluster, device_command)
        for node_id in node_ids:
            cluster.wait_for_log_length(node_id, 1)

        failed_process_id = cluster.process_id(initial_leader)
        cluster.kill_node(initial_leader)
        recovered_leader = cluster.wait_for_leader(
            excluded_node_ids=frozenset({initial_leader})
        )
        mode_commit = _commit(cluster, mode_command)
        duplicate_mode_commit = _commit(cluster, mode_command)

        restarted_process_id = cluster.start_node(initial_leader)
        node_logs = {
            node_id: cluster.wait_for_log_length(node_id, 2) for node_id in node_ids
        }

        projections = {
            node_id: _project(commands) for node_id, commands in node_logs.items()
        }
        rpc_device_read = _read_device_over_rpc(
            projections[recovered_leader],
            device.id,
        )
        durable_result = _prove_durable_mode_restart(
            root / "delivery",
            device_command,
            mode_command,
        )

        return {
            "schema_version": _ARTIFACT_SCHEMA_VERSION,
            "manyfold_installation": _manyfold_installation(),
            "raft": {
                "node_count": len(node_ids),
                "initial_process_ids": initial_process_ids,
                "initial_leader": initial_leader,
                "failed_process_id": failed_process_id,
                "recovered_leader": recovered_leader,
                "restarted_process_id": restarted_process_id,
                "leader_changed": recovered_leader != initial_leader,
                "restarted_process_changed": (
                    restarted_process_id != failed_process_id
                ),
                "device_sequence": device_commit["sequence"],
                "mode_sequence": mode_commit["sequence"],
                "duplicate_mode_sequence": duplicate_mode_commit["sequence"],
                "node_command_ids": {
                    node_id: [command["command_id"] for command in commands]
                    for node_id, commands in node_logs.items()
                },
                "node_revisions": {
                    node_id: projection.revision
                    for node_id, projection in projections.items()
                },
            },
            "world_rpc": {
                "revision": rpc_device_read.revision,
                "device_id": rpc_device_read.device.id
                if rpc_device_read.device is not None
                else None,
                "capabilities": list(rpc_device_read.device.capabilities)
                if rpc_device_read.device is not None
                else [],
            },
            "durable_delivery": durable_result,
            "boundary": {
                "raft_command_kinds": sorted(COORDINATED_COMMAND_KINDS),
                "durable_channel": MODE_DELIVERY_CHANNEL,
                "excluded_hot_path_data": sorted(EXCLUDED_DURABLE_DATA_KINDS),
            },
        }


@final
class _RpcProof:
    def __init__(self, state: WorldState) -> None:
        server_transport, client_transport = _transport_pair(
            server_node_id="world-server",
            client_node_id="world-client",
        )
        self._transports = (server_transport, client_transport)
        self._server_endpoint = RpcEndpoint(server_transport)
        self._client_endpoint = RpcEndpoint(client_transport)
        if not self._server_endpoint.wait_until_ready(timeout=2.0):
            raise TimeoutError("world RPC server handshake did not complete")
        if not self._client_endpoint.wait_until_ready(timeout=2.0):
            raise TimeoutError("world RPC client handshake did not complete")
        self._server = WorldRpcServer(self._server_endpoint, state)
        self.client = WorldRpcClient(self._client_endpoint)

    def close(self) -> None:
        self._server.dispose()
        self._client_endpoint.close()
        self._server_endpoint.close()
        for transport in reversed(self._transports):
            transport.close()


def _commit(
    cluster: DevelopmentCluster,
    command: ControlCommand,
) -> dict[str, object]:
    return cluster.commit(
        command.kind,
        command.payload,
        command_id=command.command_id,
        timeout_seconds=10.0,
    )


def _project(commands: tuple[dict[str, object], ...]) -> WorldState:
    state = WorldState()
    state.apply_log(_committed(command) for command in commands)
    return state


def _committed(value: dict[str, object]) -> CommittedCommand:
    sequence = value.get("sequence")
    command_id = value.get("command_id")
    kind = value.get("kind")
    payload = value.get("payload")
    if (
        isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or not isinstance(command_id, str)
        or not isinstance(kind, str)
        or not isinstance(payload, dict)
    ):
        raise ValueError(f"invalid ManyFold committed command {value!r}")
    return CommittedCommand(sequence, command_id, kind, payload)


def _read_device_over_rpc(
    state: WorldState,
    device_id: str,
) -> WorldDeviceRead:
    proof = _RpcProof(state)
    try:
        return proof.client.get_device(device_id, timeout_seconds=2.0)
    finally:
        proof.close()


def _prove_durable_mode_restart(
    root: Path,
    device_command: ControlCommand,
    mode_command: ControlCommand,
) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    state = WorldState()
    state.apply(_as_committed(1, device_command))
    committed_mode = _as_committed(2, mode_command)
    sender_transport, receiver_transport = _transport_pair()
    sender = DurableDelivery(
        sender_transport,
        _delivery_config(root / "sender.sqlite3"),
    )
    receiver = DurableDelivery(
        receiver_transport,
        _delivery_config(root / "receiver.sqlite3"),
    )
    sender.send(
        mode_delivery_message(committed_mode),
        message_id=committed_mode.command_id,
    )
    received_before_restart = receiver.receive(timeout=2.0)
    receiver.close()
    receiver_transport.close()

    restarted_transport = TcpTransport.listen(
        NodeIdentity("heart", "receiver", "receiver-2"),
        receiver_transport.address,
        config=_transport_config(),
        expected_peer_node_id="sender",
    )
    restarted = DurableDelivery(
        restarted_transport,
        _delivery_config(root / "receiver.sqlite3"),
    )
    try:
        if not restarted_transport.wait_until_connected(timeout=2.0):
            raise TimeoutError("durable receiver did not reconnect")
        applied_count = int(
            apply_delivered_mode(
                state,
                restarted,
                timeout_seconds=2.0,
            )
        )
        if not sender.flush(timeout=2.0):
            raise TimeoutError("durable sender did not observe the mode ACK")
        try:
            restarted.receive(timeout=0.1)
        except TimeoutError:
            duplicate_exposed = False
        else:
            duplicate_exposed = True
        return {
            "message_id": committed_mode.command_id,
            "received_before_restart": received_before_restart.message_id,
            "receiver_restarted": True,
            "applied_count": applied_count,
            "duplicate_exposed_after_ack": duplicate_exposed,
            "sender_outbox_items": sender.health().outbox_items,
            "receiver_acknowledgements": (restarted.health().acknowledgements),
            "revision": state.revision,
        }
    finally:
        restarted.close()
        restarted_transport.close()
        sender.close()
        sender_transport.close()


def _transport_pair(
    *,
    server_node_id: str = "receiver",
    client_node_id: str = "sender",
) -> tuple[TcpTransport, TcpTransport]:
    server = TcpTransport.listen(
        NodeIdentity("heart", server_node_id, f"{server_node_id}-1"),
        config=_transport_config(),
        expected_peer_node_id=client_node_id,
    )
    client = TcpTransport.connect(
        NodeIdentity("heart", client_node_id, f"{client_node_id}-1"),
        server.address,
        config=_transport_config(),
        expected_peer_node_id=server_node_id,
    )
    if not server.wait_until_connected(timeout=2.0):
        raise TimeoutError(f"{server_node_id} transport did not connect")
    if not client.wait_until_connected(timeout=2.0):
        raise TimeoutError(f"{client_node_id} transport did not connect")
    return client, server


def _transport_config() -> TransportConfig:
    return TransportConfig(
        security=TransportSecurity.insecure_local_development(),
        outbound_queue_limit=16,
        inbound_queue_limit=16,
        max_payload_bytes=65536,
        connect_timeout=0.1,
        handshake_timeout=0.5,
        heartbeat_interval=0.05,
        peer_timeout=0.5,
        reconnect=ReconnectPolicy(0.02, 1.5, 0.1),
    )


def _delivery_config(path: Path) -> DeliveryConfig:
    return DeliveryConfig(
        path,
        max_outbox_items=16,
        max_inbox_items=16,
        max_storage_bytes=1024 * 1024,
        receive_queue_limit=4,
        max_message_bytes=4096,
        message_ttl_seconds=5.0,
        dedupe_retention_seconds=5.0,
        retry_initial_seconds=0.05,
        retry_multiplier=1.5,
        retry_max_seconds=0.1,
    )


def _as_committed(
    sequence: int,
    command: ControlCommand,
) -> CommittedCommand:
    return CommittedCommand(
        sequence=sequence,
        command_id=command.command_id,
        kind=command.kind,
        payload=command.payload,
    )


def _device() -> WorldDevice:
    return WorldDevice(
        id="totem3",
        position=WorldPosition(0.0, 0.0, 0.0),
        dimensions=WorldDimensions(0.5, 2.0, 0.5),
        capabilities=("hub75", "gamepad"),
    )


def _active_mode() -> ActiveMode:
    return ActiveMode(
        mode_id="mandelbulb",
        configuration_id="lib-2026",
        owner_device_id="totem3",
    )


def _manyfold_installation() -> dict[str, object]:
    installed_distribution = distribution("manyfold")
    direct_url_text = installed_distribution.read_text("direct_url.json")
    direct_url_value = (
        json.loads(direct_url_text) if direct_url_text is not None else None
    )
    if direct_url_value is not None and not isinstance(direct_url_value, dict):
        raise ValueError("manyfold direct_url.json must contain a JSON object")
    direct_url = direct_url_value or {}
    url = direct_url.get("url")
    if "vcs_info" in direct_url:
        install_kind = "vcs"
    elif isinstance(url, str) and url.endswith(".whl"):
        install_kind = "wheel"
    else:
        install_kind = "index"
    return {
        "distribution_version": installed_distribution.version,
        "install_kind": install_kind,
        "installation_root": str(
            Path(str(installed_distribution.locate_file(""))).resolve()
        ),
        "direct_url": direct_url_value,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the machine-readable JSON proof artifact.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    with tempfile.TemporaryDirectory(
        prefix="heart-manyfold-coordination-"
    ) as directory:
        artifact = run_proof(Path(directory))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(
        f"{json.dumps(artifact, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
