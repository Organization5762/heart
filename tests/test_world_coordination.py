from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_three_process_world_coordination_proof(tmp_path: Path) -> None:
    artifact_path = tmp_path / "coordination.json"
    subprocess.run(
        (
            sys.executable,
            "scripts/verify_manyfold_world_coordination.py",
            "--output",
            str(artifact_path),
        ),
        check=True,
        timeout=30,
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert artifact["schema_version"] == 1
    assert artifact["manyfold_installation"]["distribution_version"]
    assert artifact["manyfold_installation"]["install_kind"] in {
        "index",
        "vcs",
        "wheel",
    }
    assert artifact["manyfold_installation"]["installation_root"]
    assert artifact["raft"]["node_count"] == 3
    assert artifact["raft"]["leader_changed"]
    assert artifact["raft"]["restarted_process_changed"]
    assert artifact["raft"]["mode_sequence"] == 2
    assert artifact["raft"]["duplicate_mode_sequence"] == 2
    assert set(artifact["raft"]["node_revisions"].values()) == {2}
    assert artifact["world_rpc"]["revision"] == 2
    assert artifact["world_rpc"]["device_id"] == "totem3"
    assert artifact["durable_delivery"]["receiver_restarted"]
    assert artifact["durable_delivery"]["applied_count"] == 1
    assert artifact["durable_delivery"]["receiver_acknowledgements"] == 1
    assert not artifact["durable_delivery"]["duplicate_exposed_after_ack"]
    assert artifact["durable_delivery"]["sender_outbox_items"] == 0
    assert artifact["boundary"]["excluded_hot_path_data"] == [
        "debug",
        "frame_tick",
        "microphone_sample",
        "navigation_event",
        "rendered_frame",
        "sensor_sample",
    ]
