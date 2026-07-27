from __future__ import annotations

import base64
import html
import json
from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import final

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from heart.testing.state_similarity import JsonValue, canonicalize_state

CONTRACT_SCHEMA_VERSION = 1
SYSTEM_CONTRACT_SCENARIO_ID = "heart-world-coordination-node-failure-v1"
SYSTEM_CONTRACT_SEED = "heart-world-coordination-deterministic-v1"
SYSTEM_CONTRACT_RGB_WIDTH = 8

_PASS = (57, 211, 140)
_BOUND = (143, 199, 255)
_GAP = (212, 167, 44)
_FAIL = (255, 123, 114)

_EXPECTED_HOT_PATH_EXCLUSIONS = [
    "debug",
    "frame_tick",
    "microphone_sample",
    "navigation_event",
    "rendered_frame",
    "sensor_sample",
]

_API_GAPS: tuple[tuple[str, str], ...] = (
    (
        "peer_discovered_connected_recovered",
        "Heart exposes these through heart.node.status changed snapshots, but "
        "not as distinct ordered peer lifecycle events.",
    ),
    (
        "transport_retry_scheduled_attempted",
        "World coordination exposes final durable transport state but not "
        "ordered public retry scheduled/attempted events.",
    ),
    (
        "durable_queued_retry_replay_acknowledged",
        "Durable delivery exposes health counters and received messages, but no "
        "public PubSub lifecycle topic for queued, retried, or acknowledged "
        "records.",
    ),
    (
        "watermark_coalesced_dropped_expired",
        "No public Heart or ManyFold event in this qualification trace currently "
        "reports watermark coalescing, drops, or expiry.",
    ),
    (
        "signer_renewal_restart",
        "Signer renewal and restart are visible through status and health calls, "
        "but not through a public lifecycle event topic.",
    ),
    (
        "raft_leader_change",
        "Raft leader changes are visible through coordinator or DevelopmentCluster "
        "status, but not through a public ordered leader-change topic.",
    ),
    (
        "clean_shutdown_stopped",
        "Heart publishes stopping but not a terminal stopped lifecycle event "
        "after resources close.",
    ),
)

_STYLE = """
:root{color-scheme:dark;font-family:ui-sans-serif,system-ui,sans-serif;background:#111318;color:#edf0f7}
body{margin:0 auto;max-width:1200px;padding:2rem}
section{background:#1a1e27;border:1px solid #303746;border-radius:8px;margin:1rem 0;padding:1rem}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #303746;padding:.5rem;text-align:left}
pre{background:#0d0f14;border-radius:8px;max-height:28rem;overflow:auto;padding:1rem}
.frame{background:#07080b;border-radius:8px;overflow:auto;padding:1rem}.frame img{display:block;image-rendering:pixelated;width:640px}
"""


@final
@dataclass(frozen=True)
class SystemContractProjection:
    state: dict[str, JsonValue]
    rgb: NDArray[np.uint8]


def project_world_coordination_contract(
    artifact: Mapping[str, object],
) -> SystemContractProjection:
    """Project a ManyFold world-coordination artifact into stable contract data."""

    raft = _object(artifact, "raft")
    durable = _object(artifact, "durable_delivery")
    world_rpc = _object(artifact, "world_rpc")
    boundary = _object(artifact, "boundary")

    node_revisions = _string_ints(raft, "node_revisions")
    expected_revision = _integer(world_rpc, "revision")
    mode_sequence = _integer(raft, "mode_sequence")
    duplicate_sequence = _integer(raft, "duplicate_mode_sequence")
    acknowledgements = _integer(durable, "receiver_acknowledgements")
    outbox_items = _integer(durable, "sender_outbox_items")
    observed_revisions = sorted(set(node_revisions.values()))

    checks = {
        "leader_changed": _boolean(raft, "leader_changed"),
        "restarted_process_changed": _boolean(raft, "restarted_process_changed"),
        "revisions_converged": observed_revisions == [expected_revision],
        "rpc_read_matches_revision": expected_revision == 2,
        "durable_receiver_restarted": _boolean(durable, "receiver_restarted"),
        "durable_item_applied_once": _integer(durable, "applied_count") == 1,
        "durable_replay_acknowledged": acknowledgements >= 1,
        "durable_sender_outbox_drained": outbox_items == 0,
        "no_duplicate_mode_commit": duplicate_sequence == mode_sequence,
        "no_duplicate_after_ack": not _boolean(durable, "duplicate_exposed_after_ack"),
        "no_hot_path_data_in_durable_contract": (
            _strings(boundary, "excluded_hot_path_data")
            == _EXPECTED_HOT_PATH_EXCLUSIONS
        ),
    }
    state = canonicalize_state(
        {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "scenario": _scenario(artifact, node_revisions),
            "event_timeline": _timeline(
                node_count=_integer(raft, "node_count"),
                mode_sequence=mode_sequence,
            ),
            "role_by_failure_impact_matrix": _impact_matrix(checks),
            "bounds": [
                {
                    "name": "raft_revision_convergence",
                    "expected_revision": expected_revision,
                    "observed_revisions": observed_revisions,
                    "passed": checks["revisions_converged"],
                },
                {
                    "name": "duplicate_command_coalescence",
                    "original_sequence": mode_sequence,
                    "duplicate_sequence": duplicate_sequence,
                    "passed": checks["no_duplicate_mode_commit"],
                },
                {
                    "name": "durable_ack_convergence",
                    "acknowledgements": acknowledgements,
                    "sender_outbox_items": outbox_items,
                    "passed": (
                        checks["durable_replay_acknowledged"]
                        and checks["durable_sender_outbox_drained"]
                    ),
                },
            ],
            "negative_assertions": [
                _check("no_duplicate_mode_commit", checks),
                _check("no_duplicate_after_ack", checks),
                _check("no_hot_path_data_in_durable_contract", checks),
            ],
            "api_gaps": [
                {"transition": transition, "gap": gap, "passed": False}
                for transition, gap in _API_GAPS
            ],
        }
    )
    if not isinstance(state, dict):
        raise TypeError("system contract projection must canonicalize to an object")
    return SystemContractProjection(state=state, rgb=render_system_contract_rgb(state))


def render_system_contract_rgb(state: Mapping[str, JsonValue]) -> NDArray[np.uint8]:
    rows: list[tuple[int, int, int]] = []
    for section in (
        "event_timeline",
        "role_by_failure_impact_matrix",
        "bounds",
        "negative_assertions",
        "api_gaps",
    ):
        rows.extend(_row_colors(state.get(section)))
    if not rows:
        rows.append(_FAIL)
    return np.repeat(
        np.asarray(rows, dtype=np.uint8)[:, np.newaxis, :],
        SYSTEM_CONTRACT_RGB_WIDTH,
        axis=1,
    )


def write_system_contract_review(
    artifact: Mapping[str, object],
    output_path: str | Path,
) -> Path:
    projection = project_world_coordination_contract(artifact)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(system_contract_review_html(projection), encoding="utf-8")
    return path


def system_contract_review_html(projection: SystemContractProjection) -> str:
    state = projection.state
    scenario = state.get("scenario", {})
    title = (
        str(scenario.get("id", "system contract"))
        if isinstance(scenario, Mapping)
        else "system contract"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(title)} · System contract</title><style>{_STYLE}</style></head><body>
<h1>{_escape(title)}</h1>
<section><h2>Scenario Metadata</h2><pre><code>{_json_html(scenario)}</code></pre></section>
<section><h2>RGB Contract Strip</h2><div class="frame"><img alt="System contract RGB strip" src="{_png_data_uri(projection.rgb)}"></div></section>
<section><h2>Event Timeline</h2>{_table(state.get("event_timeline"), ("step", "topic", "transition", "state"))}</section>
<section><h2>Role By Failure Impact Matrix</h2>{_table(state.get("role_by_failure_impact_matrix"), ("role", "failure", "observable_transition", "expected_state", "passed"))}</section>
<section><h2>Bounds And Negative Assertions</h2>{_table(_joined(state.get("bounds"), state.get("negative_assertions")), ("name", "passed"))}</section>
<section><h2>Public API Gaps</h2>{_table(state.get("api_gaps"), ("transition", "gap", "passed"))}</section>
</body></html>
"""


def _scenario(
    artifact: Mapping[str, object],
    node_revisions: Mapping[str, int],
) -> dict[str, object]:
    return {
        "id": SYSTEM_CONTRACT_SCENARIO_ID,
        "seed": SYSTEM_CONTRACT_SEED,
        "source_protocol": artifact.get(
            "protocol",
            "heart.manyfold-world-coordination-proof",
        ),
        "node_ids": sorted(node_revisions),
        "clock": {"type": "real_runtime_bounded", "semantic_bounds_only": True},
    }


def _timeline(*, node_count: int, mode_sequence: int) -> list[dict[str, object]]:
    return [
        _event(1, "manyfold.lifecycle.raft", "cluster_started", "started", node_count),
        _event(2, "manyfold.raft.log", "device_state_committed", "revision_1"),
        _event(
            3,
            "manyfold.lifecycle.raft",
            "leader_process_failed",
            "failed_leader_unavailable",
            role="failed_leader",
        ),
        _event(4, "manyfold.lifecycle.raft", "leader_changed", "replacement_elected"),
        _event(
            5,
            "manyfold.raft.log",
            "mode_state_committed_after_failure",
            f"revision_{mode_sequence}",
        ),
        _event(
            6,
            "manyfold.durable_delivery",
            "durable_item_queued",
            "committed_mode_command",
        ),
        _event(
            7,
            "manyfold.durable_delivery",
            "receiver_restarted_before_ack",
            "receiver_restarted",
        ),
        _event(
            8,
            "manyfold.durable_delivery",
            "replay_acknowledged",
            "sender_outbox_drained",
        ),
    ]


def _event(
    step: int,
    topic: str,
    transition: str,
    state: str,
    node_count: int | None = None,
    *,
    role: str | None = None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "step": step,
        "topic": topic,
        "transition": transition,
        "state": state,
        "passed": True,
    }
    if node_count is not None:
        event["node_count"] = node_count
    if role is not None:
        event["role"] = role
    return event


def _impact_matrix(checks: Mapping[str, bool]) -> list[dict[str, object]]:
    return [
        _impact(
            "failed_leader",
            "process_killed",
            "leader_changed",
            "restarted_and_converged",
            checks["leader_changed"]
            and checks["restarted_process_changed"]
            and checks["revisions_converged"],
        ),
        _impact(
            "replacement_leader",
            "leader_loss",
            "mode_commit_after_failure",
            "world_rpc_reads_revision_2",
            checks["leader_changed"] and checks["rpc_read_matches_revision"],
        ),
        _impact(
            "durable_receiver",
            "restart_before_ack",
            "replay_acknowledged",
            "applied_once_outbox_empty",
            checks["durable_receiver_restarted"]
            and checks["durable_item_applied_once"]
            and checks["durable_replay_acknowledged"]
            and checks["durable_sender_outbox_drained"]
            and checks["no_duplicate_after_ack"],
        ),
        _impact(
            "all_nodes",
            "duplicate_mode_command",
            "duplicate_command_coalesced",
            "single_mode_revision",
            checks["no_duplicate_mode_commit"],
        ),
    ]


def _impact(
    role: str,
    failure: str,
    transition: str,
    expected_state: str,
    passed: bool,
) -> dict[str, object]:
    return {
        "role": role,
        "failure": failure,
        "observable_transition": transition,
        "expected_state": expected_state,
        "passed": passed,
    }


def _check(name: str, checks: Mapping[str, bool]) -> dict[str, object]:
    return {"name": name, "passed": checks[name]}


def _row_colors(value: object) -> list[tuple[int, int, int]]:
    if not isinstance(value, list):
        return []
    rows: list[tuple[int, int, int]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        if "gap" in item:
            rows.append(_GAP)
        elif item.get("passed") is not True:
            rows.append(_FAIL)
        elif "expected_revision" in item or "original_sequence" in item:
            rows.append(_BOUND)
        else:
            rows.append(_PASS)
    return rows


def _object(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise ValueError(f"qualification artifact field {key!r} must be an object")
    return item


def _string_ints(value: Mapping[str, object], key: str) -> dict[str, int]:
    raw = _object(value, key)
    result: dict[str, int] = {}
    for item_key, item_value in raw.items():
        if not isinstance(item_key, str):
            raise ValueError(f"{key} keys must be strings")
        if isinstance(item_value, bool) or not isinstance(item_value, int):
            raise ValueError(f"{key}.{item_key} must be an integer")
        result[item_key] = item_value
    return result


def _strings(value: Mapping[str, object], key: str) -> list[str]:
    raw = value.get(key)
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"qualification artifact field {key!r} must be a string list")
    return sorted(raw)


def _integer(value: Mapping[str, object], key: str) -> int:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"qualification artifact field {key!r} must be an integer")
    return raw


def _boolean(value: Mapping[str, object], key: str) -> bool:
    raw = value.get(key)
    if not isinstance(raw, bool):
        raise ValueError(f"qualification artifact field {key!r} must be a boolean")
    return raw


def _table(value: object, columns: tuple[str, ...]) -> str:
    rows = [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []
    heading = "".join(f"<th>{_escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{_escape(str(row.get(column, '')))}</td>" for column in columns)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table>"


def _joined(first: object, second: object) -> list[object]:
    rows: list[object] = []
    if isinstance(first, list):
        rows.extend(first)
    if isinstance(second, list):
        rows.extend(second)
    return rows


def _png_data_uri(rgb: NDArray[np.uint8]) -> str:
    output = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(output, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(output.getvalue()).decode('ascii')}"


def _json_html(value: object) -> str:
    return _escape(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
