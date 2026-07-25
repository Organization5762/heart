from __future__ import annotations

import json
import multiprocessing
import os
import queue
import socket
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from manyfold.architecture import (MachineSignerService, NodeIdentityStore,
                                   PubSubTopic)

from heart.peripheral.core.input.debug import InputDebugTap
from heart.peripheral.core.input.external_sensors import (
    ExternalSensorHub, external_sensor_state_topic)
from heart.peripheral.core.input.profiles.navigation import (
    HEART_INPUT_PUBSUB, NAVIGATION_TOPIC, NavigationEvent)
from heart.runtime.manyfold_node import (EXTERNAL_SENSOR_STATE_TOPIC,
                                         FRAME_TICK_TOPIC,
                                         HEART_MANYFOLD_STATUS_TOPIC,
                                         HEART_TOPIC_POLICIES,
                                         INPUT_EVENT_TOPIC,
                                         MICROPHONE_SAMPLE_STREAM,
                                         RENDERED_FRAME_STREAM,
                                         ManyfoldNodeConfig,
                                         ManyfoldNodeRuntime, TopicDelivery,
                                         topic_policy_manifest)

MANYFOLD_MESH_BASE_COMMIT = "726f64d72b36d8bd134bda63e29ebd80472736b6"
CLUSTER_ID = "heart-mesh-test"
LOCAL_HOST = "127.0.0.1"
SWIM_KEY_A = "a1" * 32
SWIM_KEY_B = "b2" * 32
PROCESS_TIMEOUT_SECONDS = 15.0
CONVERGENCE_TIMEOUT_SECONDS = 10.0
POLL_LATENCY_LIMIT_SECONDS = 0.05


@dataclass
class _NodeProcess:
    node_id: str
    process: multiprocessing.Process
    commands: Any
    reports: Any


@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real socket loss/restart qualification runs serially with -n 0",
)
def test_real_process_mesh_story(tmp_path: Path) -> None:
    """Exercise one signed discovery, SWIM, mesh, loss, and reconnect story."""
    (
        signer_a,
        signer_b,
        signer_socket_a,
        signer_socket_b,
        signer_directory,
    ) = _start_signers(tmp_path)
    bootstrap_port_a = _unused_port()
    bootstrap_port_b = _unused_port()
    mesh_port_b = _unused_port()
    config_a = tmp_path / "node-a.json"
    config_b = tmp_path / "node-b.json"
    _write_node_config(
        config_a,
        node_id="node-a",
        instance_id="instance-a-1",
        incarnation=0,
        bootstrap_port=bootstrap_port_a,
        signer_socket=signer_socket_a,
        swim_key_hex=SWIM_KEY_A,
        peer_node_id="node-b",
        peer_bootstrap_port=bootstrap_port_b,
        peer_mesh_port=mesh_port_b,
        peer_swim_key_hex=SWIM_KEY_B,
        mesh_role="connect",
    )
    _write_node_config(
        config_b,
        node_id="node-b",
        instance_id="instance-b-1",
        incarnation=0,
        bootstrap_port=bootstrap_port_b,
        signer_socket=signer_socket_b,
        swim_key_hex=SWIM_KEY_B,
        peer_node_id="node-a",
        peer_bootstrap_port=bootstrap_port_a,
        peer_mesh_port=mesh_port_b,
        peer_swim_key_hex=SWIM_KEY_A,
        mesh_role="listen",
        mesh_listen_port=mesh_port_b,
    )

    node_a: _NodeProcess | None = None
    node_b: _NodeProcess | None = None
    restarted_b: _NodeProcess | None = None
    try:
        node_a = _start_node("node-a", config_a)
    except BaseException:
        signer_b.stop()
        signer_a.stop()
        signer_directory.cleanup()
        raise
    assert node_a is not None
    try:
        discovered = _wait_snapshot(
            node_a,
            lambda snapshot: (
                snapshot["candidate_count"] == 1
                and snapshot["authenticated_peers"] == []
                and "node-b" not in snapshot["members"]
            ),
        )
        assert discovered["candidate_count"] == 1
        assert discovered["authenticated_peers"] == []
        assert "node-b" not in discovered["members"]

        node_b = _start_node("node-b", config_b)
        connected_a = _wait_snapshot(node_a, _connected_to("node-b"))
        connected_b = _wait_snapshot(node_b, _connected_to("node-a"))
        assert connected_a["members"]["node-b"]["state"] == "alive"
        assert connected_b["members"]["node-a"]["state"] == "alive"
        assert connected_a["remote_subscriptions"] == 3
        assert connected_b["remote_subscriptions"] == 3

        _command(node_a, "navigation", source="mesh-test.first", step=1)
        _wait_snapshot(
            node_b,
            lambda snapshot: (
                _event_count(
                    snapshot["navigation_events"],
                    source="mesh-test.first",
                )
                == 1
            ),
        )
        _command(
            node_a,
            "sensor",
            sensor_key="mesh-accelerometer:x",
            value=0.25,
        )
        _wait_snapshot(
            node_b,
            lambda snapshot: (
                _sensor_count(
                    snapshot["sensor_events"],
                    sensor_key="mesh-accelerometer:x",
                    value=0.25,
                )
                == 1
            ),
        )
        first_a = _wait_snapshot(node_a, lambda _snapshot: True)
        first_b = _wait_snapshot(node_b, lambda _snapshot: True)
        assert (
            _event_count(
                first_a["navigation_events"],
                source="mesh-test.first",
            )
            == 1
        )
        assert (
            _event_count(
                first_b["navigation_events"],
                source="mesh-test.first",
            )
            == 1
        )
        assert (
            _sensor_count(
                first_a["sensor_events"],
                sensor_key="mesh-accelerometer:x",
                value=0.25,
            )
            == 1
        )
        assert (
            _sensor_count(
                first_b["sensor_events"],
                sensor_key="mesh-accelerometer:x",
                value=0.25,
            )
            == 1
        )

        node_b.process.terminate()
        node_b.process.join(PROCESS_TIMEOUT_SECONDS)
        assert not node_b.process.is_alive()
        loss = _wait_snapshot(
            node_a,
            lambda snapshot: (
                snapshot["members"].get("node-b", {}).get("state") == "dead"
                and snapshot["mesh_peer_links"].get("node-b") == "reconnecting"
            ),
        )
        loss = _wait_snapshot(
            node_a,
            lambda snapshot: any(
                event["event_type"] == "changed"
                and '"node_id":"node-b"' in event["members_json"]
                and '"state":"dead"' in event["members_json"]
                for event in snapshot["status_events"]
            ),
        )
        assert loss["max_poll_seconds"] < POLL_LATENCY_LIMIT_SECONDS
        assert any(
            event["event_type"] == "changed"
            and '"node_id":"node-b"' in event["members_json"]
            and '"state":"dead"' in event["members_json"]
            for event in loss["status_events"]
        )

        _write_node_config(
            config_b,
            node_id="node-b",
            instance_id="instance-b-2",
            incarnation=1,
            bootstrap_port=bootstrap_port_b,
            signer_socket=signer_socket_b,
            swim_key_hex=SWIM_KEY_B,
            peer_node_id="node-a",
            peer_bootstrap_port=bootstrap_port_a,
            peer_mesh_port=mesh_port_b,
            peer_swim_key_hex=SWIM_KEY_A,
            mesh_role="listen",
            mesh_listen_port=mesh_port_b,
        )
        restarted_b = _start_node("node-b", config_b)
        reconnected_a = _wait_snapshot(
            node_a,
            lambda snapshot: (
                _connected_to("node-b")(snapshot)
                and snapshot["members"]["node-b"]["instance_id"] == "instance-b-2"
                and snapshot["members"]["node-b"]["incarnation"] == 1
            ),
        )
        reconnected_b = _wait_snapshot(restarted_b, _connected_to("node-a"))
        assert reconnected_a["remote_subscriptions"] == 3
        assert reconnected_b["remote_subscriptions"] == 3

        _command(restarted_b, "navigation", source="mesh-test.reconnected", step=-1)
        _wait_snapshot(
            node_a,
            lambda snapshot: (
                _event_count(
                    snapshot["navigation_events"],
                    source="mesh-test.reconnected",
                )
                == 1
            ),
        )
        _command(
            restarted_b,
            "sensor",
            sensor_key="mesh-accelerometer:y",
            value=-0.5,
        )
        final_a = _wait_snapshot(
            node_a,
            lambda snapshot: (
                _sensor_count(
                    snapshot["sensor_events"],
                    sensor_key="mesh-accelerometer:y",
                    value=-0.5,
                )
                == 1
            ),
        )
        final_b = _wait_snapshot(restarted_b, lambda _snapshot: True)
        time.sleep(0.25)
        final_a = _wait_snapshot(node_a, lambda _snapshot: True)
        final_b = _wait_snapshot(restarted_b, lambda _snapshot: True)

        assert (
            _event_count(
                final_a["navigation_events"],
                source="mesh-test.reconnected",
            )
            == 1
        )
        assert (
            _event_count(
                final_b["navigation_events"],
                source="mesh-test.reconnected",
            )
            == 1
        )
        assert (
            _sensor_count(
                final_a["sensor_events"],
                sensor_key="mesh-accelerometer:y",
                value=-0.5,
            )
            == 1
        )
        assert (
            _sensor_count(
                final_b["sensor_events"],
                sensor_key="mesh-accelerometer:y",
                value=-0.5,
            )
            == 1
        )
        assert final_a["mesh_duplicate_publications"] <= 1
        assert final_b["mesh_duplicate_publications"] <= 1
        assert any(
            '"instance_id":"instance-b-2"' in event["members_json"]
            and '"state":"alive"' in event["members_json"]
            for event in final_a["status_events"]
        )

        shutdown_b = _stop_node(restarted_b)
        restarted_b = None
        shutdown_a = _stop_node(node_a)
        assert shutdown_a["manyfold_worker_threads"] == []
        assert shutdown_b["manyfold_worker_threads"] == []

        artifact = _mesh_artifact(
            discovery_snapshot=discovered,
            loss_snapshot=loss,
            first_a=first_a,
            first_b=first_b,
            final_a=final_a,
            final_b=final_b,
            shutdown_a=shutdown_a,
            shutdown_b=shutdown_b,
        )
        artifact_path = Path(
            os.environ.get(
                "HEART_MANYFOLD_TEST_ARTIFACT",
                str(tmp_path / "heart-manyfold-mesh.json"),
            )
        )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        assert artifact["durable_delivery_topics"] == []
        assert artifact["raft_topics"] == []
        assert artifact["local_only_topics"] == [
            FRAME_TICK_TOPIC,
            RENDERED_FRAME_STREAM,
            MICROPHONE_SAMPLE_STREAM,
            INPUT_EVENT_TOPIC,
        ]
    finally:
        for node in (restarted_b, node_b, node_a):
            if node is not None and node.process.is_alive():
                node.process.terminate()
                node.process.join(PROCESS_TIMEOUT_SECONDS)
        signer_b.stop()
        signer_a.stop()
        signer_directory.cleanup()


def _node_worker(config_path: str, commands: Any, reports: Any) -> None:
    runtime = ManyfoldNodeRuntime(ManyfoldNodeConfig.from_file(Path(config_path)))
    navigation_topic = PubSubTopic(
        NAVIGATION_TOPIC,
        schema=NavigationEvent,
        pubsub=HEART_INPUT_PUBSUB,
    )
    sensor_topic = external_sensor_state_topic()
    sensor_hub = ExternalSensorHub(
        InputDebugTap(history_size=0, latency_history_size=0)
    )
    navigation_events: list[dict[str, object]] = []
    sensor_events: list[dict[str, object]] = []
    status_events: list[dict[str, object]] = []
    subscriptions = [
        navigation_topic.subscribe(
            lambda event: navigation_events.append(
                {
                    "kind": str(event.kind),
                    "source": str(event.source),
                    "step": int(event.step),
                    "event_id": str(event.event_id),
                    "origin_node_id": str(event.origin_node_id),
                }
            )
        ),
        sensor_topic.subscribe(
            lambda event: sensor_events.append(
                {
                    "sensor_key": str(event.sensor_key),
                    "value": event.value,
                    "event_id": str(event.event_id),
                    "origin_node_id": str(event.origin_node_id),
                }
            )
        ),
        runtime.status_topic.subscribe(
            lambda event: status_events.append(
                {
                    "event_type": str(event.event_type),
                    "event_id": str(event.event_id),
                    "origin_node_id": str(event.origin_node_id),
                    "members_json": str(event.members_json),
                }
            )
        ),
    ]
    max_poll_seconds = 0.0
    try:
        runtime.start()
        reports.put({"kind": "ready"})
        should_run = True
        while should_run:
            try:
                command = commands.get_nowait()
            except queue.Empty:
                command = None
            if command is not None:
                command_name = command["command"]
                if command_name == "navigation":
                    navigation_topic.publish(
                        NavigationEvent(
                            kind="browse",
                            source=command["source"],
                            step=command["step"],
                        )
                    )
                elif command_name == "sensor":
                    sensor_hub.set_value(command["sensor_key"], command["value"])
                elif command_name == "snapshot":
                    reports.put(
                        _snapshot_report(
                            runtime,
                            request_id=command["request_id"],
                            navigation_events=navigation_events,
                            sensor_events=sensor_events,
                            status_events=status_events,
                            max_poll_seconds=max_poll_seconds,
                        )
                    )
                elif command_name == "stop":
                    should_run = False
                else:
                    raise ValueError(f"Unknown node command {command_name!r}")
            started_at = time.thread_time()
            runtime.poll()
            max_poll_seconds = max(
                max_poll_seconds,
                time.thread_time() - started_at,
            )
            time.sleep(0.002)
    except BaseException as error:
        reports.put(
            {
                "kind": "error",
                "error": f"{type(error).__name__}: {error}",
            }
        )
        raise
    finally:
        for subscription in reversed(subscriptions):
            subscription.dispose()
        sensor_hub.close()
        runtime.close()
        deadline = time.monotonic() + 2.0
        while _manyfold_worker_threads() and time.monotonic() < deadline:
            time.sleep(0.01)
        reports.put(
            {
                "kind": "shutdown",
                "manyfold_worker_threads": _manyfold_worker_threads(),
            }
        )


def _snapshot_report(
    runtime: ManyfoldNodeRuntime,
    *,
    request_id: str,
    navigation_events: list[dict[str, object]],
    sensor_events: list[dict[str, object]],
    status_events: list[dict[str, object]],
    max_poll_seconds: float,
) -> dict[str, object]:
    runtime_status = runtime.status()
    status = runtime_status.node
    mesh = runtime_status.mesh
    if status is None or mesh is None:
        raise RuntimeError("enabled node returned no upstream status")
    return {
        "kind": "snapshot",
        "request_id": request_id,
        "candidate_count": len(status.peers),
        "authenticated_peers": sorted(
            peer.health.remote_identity.node_id
            for peer in status.peers
            if peer.health.remote_identity is not None
            and peer.health.state.value == "connected"
        ),
        "members": {
            member.identity.node_id: {
                "instance_id": member.identity.instance_id,
                "incarnation": member.incarnation,
                "state": member.state.value,
            }
            for member in status.members
        },
        "bootstrap_peer_links": {
            peer.health.remote_identity.node_id: peer.health.state.value
            for peer in status.peers
            if peer.health.remote_identity is not None
        },
        "mesh_peer_links": {
            peer.node_id: peer.link.state.value for peer in runtime_status.mesh_peers
        },
        "remote_subscriptions": mesh.remote_subscriptions,
        "mesh_duplicate_publications": mesh.duplicate_publications,
        "navigation_events": list(navigation_events),
        "sensor_events": list(sensor_events),
        "status_events": list(status_events),
        "max_poll_seconds": max_poll_seconds,
        "last_error": next(
            (
                diagnostic.message
                for diagnostic in reversed(status.diagnostics)
                if diagnostic.severity.value == "error"
            ),
            "",
        ),
    }


def _manyfold_worker_threads() -> list[str]:
    return sorted(
        thread.name
        for thread in threading.enumerate()
        if thread is not threading.main_thread() and thread.name.startswith("manyfold")
    )


def _start_node(node_id: str, config_path: Path) -> _NodeProcess:
    context = multiprocessing.get_context("spawn")
    commands = context.Queue()
    reports = context.Queue()
    process = context.Process(
        target=_node_worker,
        args=(str(config_path), commands, reports),
        name=f"heart-mesh-{node_id}",
    )
    process.start()
    node = _NodeProcess(node_id, process, commands, reports)
    report = _wait_report(node, lambda row: row["kind"] in ("ready", "error"))
    if report["kind"] == "error":
        process.join(PROCESS_TIMEOUT_SECONDS)
        if process.is_alive():
            process.terminate()
            process.join(PROCESS_TIMEOUT_SECONDS)
        raise AssertionError(f"{node_id} failed to start: {report['error']}")
    return node


def _stop_node(node: _NodeProcess) -> dict[str, object]:
    _command(node, "stop")
    report = _wait_report(node, lambda row: row["kind"] in ("shutdown", "error"))
    node.process.join(PROCESS_TIMEOUT_SECONDS)
    assert not node.process.is_alive()
    assert node.process.exitcode == 0
    if report["kind"] == "error":
        raise AssertionError(
            f"{node.node_id} failed during shutdown: {report['error']}"
        )
    return report


def _wait_snapshot(
    node: _NodeProcess,
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    deadline = time.monotonic() + CONVERGENCE_TIMEOUT_SECONDS
    last_snapshot: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        request_id = uuid4().hex
        _command(node, "snapshot", request_id=request_id)
        report = _wait_report(
            node,
            lambda row: (
                row["kind"] == "error"
                or (row["kind"] == "snapshot" and row.get("request_id") == request_id)
            ),
        )
        if report["kind"] == "error":
            raise AssertionError(f"{node.node_id} failed: {report['error']}")
        last_snapshot = report
        if predicate(report):
            return report
        time.sleep(0.025)
    raise AssertionError(
        f"{node.node_id} did not converge; last snapshot={last_snapshot!r}"
    )


def _wait_report(
    node: _NodeProcess,
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    deadline = time.monotonic() + PROCESS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            report = node.reports.get(timeout=0.1)
        except queue.Empty:
            if not node.process.is_alive():
                raise AssertionError(
                    f"{node.node_id} exited early with {node.process.exitcode}"
                )
            continue
        if predicate(report):
            return report
    raise AssertionError(f"Timed out waiting for {node.node_id} report")


def _command(node: _NodeProcess, command: str, **fields: object) -> None:
    node.commands.put({"command": command, **fields})


def _connected_to(peer_node_id: str) -> Callable[[dict[str, Any]], bool]:
    return lambda snapshot: (
        peer_node_id in snapshot["authenticated_peers"]
        and snapshot["members"].get(peer_node_id, {}).get("state") == "alive"
        and snapshot["bootstrap_peer_links"].get(peer_node_id) == "connected"
        and snapshot["mesh_peer_links"].get(peer_node_id) == "connected"
        and snapshot["remote_subscriptions"] == 3
    )


def _event_count(events: list[dict[str, Any]], *, source: str) -> int:
    return sum(event["source"] == source for event in events)


def _sensor_count(
    events: list[dict[str, Any]],
    *,
    sensor_key: str,
    value: float,
) -> int:
    return sum(
        event["sensor_key"] == sensor_key and event["value"] == value
        for event in events
    )


def _mesh_artifact(
    *,
    discovery_snapshot: dict[str, Any],
    loss_snapshot: dict[str, Any],
    first_a: dict[str, Any],
    first_b: dict[str, Any],
    final_a: dict[str, Any],
    final_b: dict[str, Any],
    shutdown_a: dict[str, Any],
    shutdown_b: dict[str, Any],
) -> dict[str, object]:
    manifest = topic_policy_manifest()
    local_only_topics = [
        policy.topic
        for policy in HEART_TOPIC_POLICIES
        if policy.delivery is TopicDelivery.LOCAL
    ]
    return {
        "manyfold_mesh_base_commit": MANYFOLD_MESH_BASE_COMMIT,
        "authentication": "machine_signer_enrollment_mutual_tls_identity_uri",
        "process_count": 2,
        "story": {
            "discovery_candidate_untrusted_before_authentication": (
                discovery_snapshot["candidate_count"] == 1
                and not discovery_snapshot["authenticated_peers"]
                and "node-b" not in discovery_snapshot["members"]
            ),
            "swim_loss_detected": (
                loss_snapshot["members"]["node-b"]["state"] == "dead"
            ),
            "status_reported_loss_and_reconnect": (
                any(
                    '"state":"dead"' in event["members_json"]
                    for event in loss_snapshot["status_events"]
                )
                and any(
                    '"instance_id":"instance-b-2"' in event["members_json"]
                    and '"state":"alive"' in event["members_json"]
                    for event in final_a["status_events"]
                )
            ),
            "transport_reconnected": (
                final_a["bootstrap_peer_links"]["node-b"] == "connected"
                and final_b["bootstrap_peer_links"]["node-a"] == "connected"
                and final_a["mesh_peer_links"]["node-b"] == "connected"
                and final_b["mesh_peer_links"]["node-a"] == "connected"
            ),
            "subscriptions_restored": (
                final_a["remote_subscriptions"] == 3
                and final_b["remote_subscriptions"] == 3
            ),
            "shutdown_clean": (
                not shutdown_a["manyfold_worker_threads"]
                and not shutdown_b["manyfold_worker_threads"]
            ),
        },
        "navigation_counts": {
            "node_a_first": _event_count(
                first_a["navigation_events"],
                source="mesh-test.first",
            ),
            "node_b_first": _event_count(
                first_b["navigation_events"],
                source="mesh-test.first",
            ),
            "node_a_reconnected": _event_count(
                final_a["navigation_events"],
                source="mesh-test.reconnected",
            ),
            "node_b_reconnected": _event_count(
                final_b["navigation_events"],
                source="mesh-test.reconnected",
            ),
        },
        "sensor_counts": {
            "node_a_first": _sensor_count(
                first_a["sensor_events"],
                sensor_key="mesh-accelerometer:x",
                value=0.25,
            ),
            "node_b_first": _sensor_count(
                first_b["sensor_events"],
                sensor_key="mesh-accelerometer:x",
                value=0.25,
            ),
            "node_a_reconnected": _sensor_count(
                final_a["sensor_events"],
                sensor_key="mesh-accelerometer:y",
                value=-0.5,
            ),
            "node_b_reconnected": _sensor_count(
                final_b["sensor_events"],
                sensor_key="mesh-accelerometer:y",
                value=-0.5,
            ),
        },
        "topic_policy": manifest,
        "mesh_topics": [
            HEART_MANYFOLD_STATUS_TOPIC,
            NAVIGATION_TOPIC,
            EXTERNAL_SENSOR_STATE_TOPIC,
        ],
        "local_only_topics": local_only_topics,
        "durable_delivery_topics": [
            policy.topic for policy in HEART_TOPIC_POLICIES if policy.durable
        ],
        "raft_topics": [policy.topic for policy in HEART_TOPIC_POLICIES if policy.raft],
        "max_poll_seconds_during_story": max(
            final_a["max_poll_seconds"],
            final_b["max_poll_seconds"],
            loss_snapshot["max_poll_seconds"],
        ),
    }


def _start_signers(
    directory: Path,
) -> tuple[
    MachineSignerService,
    MachineSignerService,
    Path,
    Path,
    tempfile.TemporaryDirectory[str],
]:
    authority, token = NodeIdentityStore.initialize(
        directory / "node-a-identity",
        cluster_id=CLUSTER_ID,
        node_id="node-a",
        server_names=(LOCAL_HOST, "localhost"),
    )
    node_b = authority.enroll(
        directory / "node-b-identity",
        node_id="node-b",
        token=token,
        server_names=(LOCAL_HOST, "localhost"),
    )
    socket_directory = tempfile.TemporaryDirectory(prefix="heart-signers-")
    socket_root = Path(socket_directory.name)
    socket_a = socket_root / "a.sock"
    socket_b = socket_root / "b.sock"
    signer_a = MachineSignerService(
        authority,
        socket_a,
        credential_ttl_seconds=120,
    )
    signer_b = MachineSignerService(
        node_b,
        socket_b,
        credential_ttl_seconds=120,
    )
    signer_a.start()
    try:
        signer_b.start()
    except BaseException:
        signer_a.stop()
        socket_directory.cleanup()
        raise
    return signer_a, signer_b, socket_a, socket_b, socket_directory


def _write_node_config(
    path: Path,
    *,
    node_id: str,
    instance_id: str,
    incarnation: int,
    bootstrap_port: int,
    signer_socket: Path,
    swim_key_hex: str,
    peer_node_id: str,
    peer_bootstrap_port: int,
    peer_mesh_port: int,
    peer_swim_key_hex: str,
    mesh_role: str,
    mesh_listen_port: int | None = None,
) -> None:
    peer = {
        "node_id": peer_node_id,
        "bootstrap_host": LOCAL_HOST,
        "bootstrap_port": peer_bootstrap_port,
        "mesh_host": LOCAL_HOST,
        "mesh_port": peer_mesh_port,
        "swim_key_hex": peer_swim_key_hex,
        "mesh_role": mesh_role,
    }
    if mesh_listen_port is not None:
        peer["mesh_listen_host"] = LOCAL_HOST
        peer["mesh_listen_port"] = mesh_listen_port
    path.write_text(
        json.dumps(
            {
                "cluster_id": CLUSTER_ID,
                "node_id": node_id,
                "instance_id": instance_id,
                "incarnation": incarnation,
                "listen_host": LOCAL_HOST,
                "listen_port": bootstrap_port,
                "signer_socket": str(signer_socket),
                "connector_server_hostname": LOCAL_HOST,
                "swim_key_hex": swim_key_hex,
                "reconcile_interval_seconds": 0.05,
                "startup_peer_timeout_seconds": 0.05,
                "peer_absence_seconds": 0.1,
                "minimum_credential_lifetime_seconds": 30.0,
                "lease_seconds": 0.5,
                "suspect_seconds": 0.25,
                "dead_retention_seconds": 3.0,
                "swim_probe_interval_seconds": 0.05,
                "swim_ping_timeout_seconds": 0.025,
                "swim_indirect_timeout_seconds": 0.025,
                "peers": [peer],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOCAL_HOST, 0))
        return int(probe.getsockname()[1])
