from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from manyfold.architecture.transport import (FrameKind, NodeIdentity,
                                             ReconnectPolicy, TcpTransport,
                                             TransportConfig, TransportMessage,
                                             TransportSecurity)
from manyfold.architecture.transport_delivery import (DeliveryConfig,
                                                      DurableDelivery)
from manyfold.architecture.transport_rpc import RpcEndpoint
from manyfold.cluster import CommittedCommand, ControlCommand

from heart.world import (COORDINATED_COMMAND_KINDS,
                         EXCLUDED_DURABLE_DATA_KINDS, ActiveMode,
                         StaleWorldResponseError, WorldDevice, WorldDimensions,
                         WorldPosition, WorldRpcClient, WorldRpcServer,
                         WorldState, apply_delivered_mode,
                         mode_delivery_message, put_device_command,
                         select_mode_command)


class TestWorldState:
    def test_applies_device_and_mode_commands_once(self) -> None:
        state = WorldState()
        device_command = _committed(1, put_device_command("device-1", _device()))
        mode_command = _committed(
            2,
            select_mode_command("mode-1", _active_mode()),
        )

        assert state.apply(device_command)
        assert state.apply(mode_command)
        assert not state.apply(mode_command)
        assert state.device("totem3").device == _device()
        assert state.active_mode().active_mode == _active_mode()
        assert state.revision == 2

    def test_rejects_hot_path_data_and_sequence_gaps(self) -> None:
        state = WorldState()
        hot_path_command = CommittedCommand(
            sequence=1,
            command_id="frame-1",
            kind="frame_tick",
            payload={"frame": 7},
        )

        with pytest.raises(ValueError, match="outside Heart's durable"):
            state.apply(hot_path_command)
        with pytest.raises(ValueError, match="expected 1, observed 2"):
            state.apply(
                _committed(
                    2,
                    select_mode_command("mode-1", _active_mode()),
                )
            )

        assert COORDINATED_COMMAND_KINDS.isdisjoint(EXCLUDED_DURABLE_DATA_KINDS)

    def test_rejects_mode_ownership_by_an_unknown_device(self) -> None:
        state = WorldState()

        with pytest.raises(ValueError, match="not registered"):
            state.apply(
                _committed(
                    1,
                    select_mode_command("mode-1", _active_mode()),
                )
            )

    def test_validates_device_dimensions_and_capabilities(self) -> None:
        invalid_dimensions = WorldDevice(
            id="totem3",
            position=WorldPosition(0.0, 0.0, 0.0),
            dimensions=WorldDimensions(0.0, 2.0, 0.5),
        )
        duplicate_capabilities = WorldDevice(
            id="totem3",
            position=WorldPosition(0.0, 0.0, 0.0),
            dimensions=WorldDimensions(0.5, 2.0, 0.5),
            capabilities=("matrix", "matrix"),
        )

        with pytest.raises(ValueError, match="greater than zero"):
            put_device_command("invalid-dimensions", invalid_dimensions)
        with pytest.raises(ValueError, match="must be unique"):
            put_device_command("invalid-capabilities", duplicate_capabilities)


class TestWorldRpc:
    def test_reads_projected_state_over_typed_rpc(self) -> None:
        state = WorldState()
        state.apply(_committed(1, put_device_command("device-1", _device())))
        state.apply(
            _committed(
                2,
                select_mode_command("mode-1", _active_mode()),
            )
        )

        with _rpc_pair(state) as client:
            assert (
                client.get_device(
                    "totem3",
                    timeout_seconds=1.0,
                ).device
                == _device()
            )
            assert (
                client.get_active_mode(
                    timeout_seconds=1.0,
                ).active_mode
                == _active_mode()
            )
            assert client.observed_revision == 2

    def test_rejects_a_response_older_than_the_observed_revision(self) -> None:
        with _rpc_pair(WorldState(), minimum_revision=4) as client:
            with pytest.raises(StaleWorldResponseError, match="older than"):
                client.get_active_mode(timeout_seconds=1.0)


class TestWorldDurableDelivery:
    def test_restart_before_ack_delivers_and_applies_mode_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = WorldState()
            state.apply(_committed(1, put_device_command("device-1", _device())))
            committed_mode = _committed(
                2,
                select_mode_command("mode-1", _active_mode()),
            )
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

            first = receiver.receive(timeout=2.0)
            assert first.message_id == "mode-1"
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
                assert restarted_transport.wait_until_connected(timeout=2.0)
                assert apply_delivered_mode(
                    state,
                    restarted,
                    timeout_seconds=2.0,
                )
                assert sender.flush(timeout=2.0)
                with pytest.raises(TimeoutError):
                    restarted.receive(timeout=0.1)
                assert state.active_mode().active_mode == _active_mode()
                assert state.revision == 2
            finally:
                restarted.close()
                restarted_transport.close()
                sender.close()
                sender_transport.close()

    def test_rejects_non_mode_delivery_without_acknowledging_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
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
                TransportMessage(FrameKind.PUBSUB, "frame_tick", b"{}"),
                message_id="frame-1",
            )
            try:
                with pytest.raises(ValueError, match="expected channel"):
                    apply_delivered_mode(
                        WorldState(),
                        receiver,
                        timeout_seconds=2.0,
                    )
                assert sender.health().outbox_items == 1
            finally:
                receiver.close()
                sender.close()
                receiver_transport.close()
                sender_transport.close()


class _RpcPair:
    def __init__(self, state: WorldState, minimum_revision: int) -> None:
        server_transport, client_transport = _transport_pair(
            server_node_id="server",
            client_node_id="client",
        )
        self._transports = (server_transport, client_transport)
        self._server_endpoint = RpcEndpoint(server_transport)
        self._client_endpoint = RpcEndpoint(client_transport)
        assert self._server_endpoint.wait_until_ready(timeout=2.0)
        assert self._client_endpoint.wait_until_ready(timeout=2.0)
        self._server = WorldRpcServer(self._server_endpoint, state)
        self.client = WorldRpcClient(
            self._client_endpoint,
            minimum_revision=minimum_revision,
        )

    def __enter__(self) -> WorldRpcClient:
        return self.client

    def __exit__(self, *error: object) -> None:
        self._server.dispose()
        self._client_endpoint.close()
        self._server_endpoint.close()
        for transport in reversed(self._transports):
            transport.close()


def _rpc_pair(
    state: WorldState,
    *,
    minimum_revision: int = 0,
) -> _RpcPair:
    return _RpcPair(state, minimum_revision)


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
    assert server.wait_until_connected(timeout=2.0)
    assert client.wait_until_connected(timeout=2.0)
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


def _committed(sequence: int, command: ControlCommand) -> CommittedCommand:
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
