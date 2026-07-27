from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from heart.testing import assert_rgb_similar
from heart.testing.system_contract import project_world_coordination_contract

CONTRACT_GOLDEN_PATH = (
    Path(__file__).parent
    / "state_similarity"
    / "contracts"
    / "world_coordination_node_failure_expected.json"
)


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
    contract = project_world_coordination_contract(artifact)
    golden = json.loads(CONTRACT_GOLDEN_PATH.read_text(encoding="utf-8"))
    assert contract.state == golden["state"]
    assert_rgb_similar(contract.rgb, _rgb_from_rows(golden["screen"]))
    serialized_contract = json.dumps(contract.state, sort_keys=True)
    assert "initial_process_ids" not in serialized_contract
    assert "node_command_ids" not in serialized_contract
    assert "installation_root" not in serialized_contract


def _rgb_from_rows(screen: dict[str, object]) -> np.ndarray:
    rows = np.asarray(screen["rows"], dtype=np.uint8)
    shape = screen["shape"]
    assert isinstance(shape, list)
    assert shape == [len(rows), 8, 3]
    return np.repeat(rows[:, np.newaxis, :], 8, axis=1)
