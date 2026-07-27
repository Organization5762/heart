from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from heart.runtime.manyfold_qualification import API_GAPS, REQUIRED_ROLE_KINDS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_COMMAND = PROJECT_ROOT / ".venv/bin/heart-manyfold-qualification-fixture"


def test_fixture_describes_exact_public_topic_and_role_contract() -> None:
    environment = dict(os.environ)
    environment["MANYFOLD_QUALIFICATION_CANDIDATE_PYTHON"] = sys.executable
    process = subprocess.run(
        (str(FIXTURE_COMMAND),),
        cwd=PROJECT_ROOT,
        env=environment,
        input="\n".join(
            (
                json.dumps(
                    {
                        "schema_version": 1,
                        "request_id": 1,
                        "operation": "describe",
                        "payload": {},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "request_id": 2,
                        "operation": "close",
                        "payload": {},
                    }
                ),
                "",
            )
        ),
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    )
    describe, close = [
        json.loads(line)["value"] for line in process.stdout.splitlines()
    ]

    assert {role["role_kind"] for role in describe["roles"]} == set(REQUIRED_ROLE_KINDS)
    assert {contract["delivery_class"] for contract in describe["topic_contracts"]} == {
        "durable_append",
        "durable_latest",
        "volatile_latest",
        "raft_state",
    }
    assert all(
        not contract["retains_journal_rows"] and not contract["raft"]
        for contract in describe["topic_contracts"]
        if contract["delivery_class"] == "volatile_latest"
    )
    assert all(
        not contract["retains_journal_rows"] and contract["raft"]
        for contract in describe["topic_contracts"]
        if contract["delivery_class"] == "raft_state"
    )
    assert describe["api_gaps"] == list(API_GAPS)
    assert close["clean"]


def test_fixture_requires_versioned_jsonl_requests() -> None:
    process = subprocess.run(
        (str(FIXTURE_COMMAND),),
        cwd=PROJECT_ROOT,
        input=json.dumps(
            {
                "schema_version": 2,
                "request_id": "bad-version",
                "operation": "describe",
                "payload": {},
            }
        )
        + "\n",
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    )
    response = json.loads(process.stdout)

    assert not response["ok"]
    assert response["request_id"] == "bad-version"
    assert response["error"]["type"] == "ValueError"
    assert response["error"]["api_gaps"] == list(API_GAPS)
