from __future__ import annotations

from pathlib import Path

from heart.testing.system_contract import write_system_contract_review


def test_world_coordination_contract_html_renders_timeline_and_matrix(
    tmp_path: Path,
) -> None:
    path = write_system_contract_review(
        _world_artifact(),
        tmp_path / "world-contract.html",
    )

    html = path.read_text(encoding="utf-8")
    assert "heart-world-coordination-node-failure-v1" in html
    assert "leader_process_failed" in html
    assert "Role By Failure Impact Matrix" in html
    assert "transport_retry_scheduled_attempted" in html
    assert "data:image/png;base64," in html


def _world_artifact() -> dict[str, object]:
    return {
        "protocol": "heart.manyfold-world-coordination-proof",
        "schema_version": 1,
        "manyfold_installation": {
            "distribution_version": "1.0",
            "install_kind": "wheel",
            "installation_root": "/tmp/random-installation",
        },
        "raft": {
            "node_count": 3,
            "initial_process_ids": {
                "node-1": "process-random-a",
                "node-2": "process-random-b",
                "node-3": "process-random-c",
            },
            "initial_leader": "node-1",
            "failed_process_id": "process-random-a",
            "recovered_leader": "node-2",
            "restarted_process_id": "process-random-d",
            "leader_changed": True,
            "restarted_process_changed": True,
            "device_sequence": 1,
            "mode_sequence": 2,
            "duplicate_mode_sequence": 2,
            "node_command_ids": {
                "node-1": ["random-command-id-1", "random-command-id-2"],
                "node-2": ["random-command-id-1", "random-command-id-2"],
                "node-3": ["random-command-id-1", "random-command-id-2"],
            },
            "node_revisions": {
                "node-1": 2,
                "node-2": 2,
                "node-3": 2,
            },
        },
        "world_rpc": {
            "revision": 2,
            "device_id": "totem3",
            "capabilities": ["hub75", "gamepad"],
        },
        "durable_delivery": {
            "message_id": "random-command-id-2",
            "received_before_restart": "random-command-id-2",
            "receiver_restarted": True,
            "applied_count": 1,
            "duplicate_exposed_after_ack": False,
            "sender_outbox_items": 0,
            "receiver_acknowledgements": 1,
            "revision": 2,
        },
        "boundary": {
            "raft_command_kinds": [
                "heart.world.device.put",
                "heart.world.mode.select",
            ],
            "durable_channel": "heart.world.mode.delivery",
            "excluded_hot_path_data": [
                "debug",
                "frame_tick",
                "microphone_sample",
                "navigation_event",
                "rendered_frame",
                "sensor_sample",
            ],
        },
    }
