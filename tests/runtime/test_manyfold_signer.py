from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from heart.runtime.manyfold_signer import (DEFAULT_SIGNER_SOCKET,
                                           ManyfoldSignerConfig,
                                           ManyfoldSignerRuntime)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION_SCRIPT = PROJECT_ROOT / "scripts" / "qualify_manyfold_signer.py"


class TestManyfoldSignerConfig:
    def test_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HEART_MANYFOLD_SIGNER_ENABLED", raising=False)

        config = ManyfoldSignerConfig.from_environment()
        runtime = ManyfoldSignerRuntime(config)

        assert not config.enabled
        assert config.socket_path == DEFAULT_SIGNER_SOCKET
        assert runtime.start() is None
        runtime.close()

    def test_environment_contains_no_durable_key_material(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HEART_MANYFOLD_SIGNER_ENABLED", "1")
        monkeypatch.setenv("HEART_MANYFOLD_CLUSTER_ID", "heart-test")
        monkeypatch.setenv("HEART_MANYFOLD_NODE_ID", "totem-test")
        monkeypatch.setenv(
            "HEART_MANYFOLD_SIGNER_SOCKET",
            "/tmp/heart-signer-test.sock",
        )

        config = ManyfoldSignerConfig.from_environment()

        assert config.enabled
        assert config.cluster_id == "heart-test"
        assert config.node_id == "totem-test"
        assert "private_key" not in repr(config)
        assert "certificate_pem" not in repr(config)

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("retry_max_attempts", 6, "between 1 and 5"),
            ("retry_delay_seconds", 1.1, "between 0 and 1"),
        ],
    )
    def test_rejects_policy_outside_manyfold_bounds(
        self,
        field: str,
        value: float,
        message: str,
    ) -> None:
        arguments = {
            "enabled": True,
            "socket_path": DEFAULT_SIGNER_SOCKET,
            "cluster_id": "heart-test",
            "node_id": "totem-test",
            field: value,
        }

        with pytest.raises(ValueError, match=message):
            ManyfoldSignerConfig(**arguments)


@pytest.mark.timeout(30)
def test_real_multiprocess_signer_qualification(tmp_path: Path) -> None:
    signer_executable = Path(sys.executable).with_name("manyfold-machine-signer")
    enrollment_executable = Path(sys.executable).with_name("manyfold-enrollment")
    artifact_path = tmp_path / "qualification.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(QUALIFICATION_SCRIPT),
            "--signer-executable",
            str(signer_executable),
            "--enrollment-executable",
            str(enrollment_executable),
            "--output",
            str(artifact_path),
        ],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
        check=True,
        capture_output=True,
        text=True,
        timeout=25,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["ipc_permissions"] == {
        "state_directory_mode": "0700",
        "socket_parent_mode": "0700",
        "socket_mode": "0600",
    }
    assert artifact["enrollment_token_file_removed"]
    serialized_commands = json.dumps(artifact["commands"])
    assert "--token-file" in serialized_commands
    assert '"--token"' not in serialized_commands
    assert "BEGIN PRIVATE KEY" not in completed.stderr
    assert "BEGIN EC PRIVATE KEY" not in completed.stderr
    for private_key_file in artifact["durable_private_key_files"]:
        assert Path(private_key_file).name not in completed.stderr
    assert artifact["bootstrap"]["client_processes"] == 2
    assert artifact["bootstrap"]["states"] == ["ready", "ready"]
    assert not artifact["bootstrap"]["durable_private_key_opened_by_clients"]
    assert (
        artifact["restart_renewal"]["during_outage"]["state"]
        == "renewal_failed"
    )
    assert artifact["restart_renewal"]["during_outage"]["is_usable"]
    assert artifact["restart_renewal"]["after_restart"]["generation"] == 2
    assert artifact["restart_renewal"]["after_expiry"]["state"] == "expired"
    assert not artifact["restart_renewal"]["after_expiry"]["is_usable"]
    assert artifact["unauthorized"]["state"] == "rejected"
    assert artifact["unauthorized"]["credential_state"] == "unavailable"
    assert artifact["unavailable_bootstrap"]["state"] == "rejected"
    assert artifact["unavailable_bootstrap"]["credential_state"] == "unavailable"
    serialized_artifact = json.dumps(artifact)
    assert "BEGIN PRIVATE KEY" not in serialized_artifact
    assert "BEGIN EC PRIVATE KEY" not in serialized_artifact
