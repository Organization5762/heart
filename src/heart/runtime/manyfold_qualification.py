"""ManyFold exact-wheel JSONL supervisor for Heart's real application roles."""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import socket
import subprocess
import sys
import time
from collections.abc import Mapping
from importlib.metadata import distribution
from pathlib import Path
from typing import IO, final
from urllib.parse import unquote, urlparse

from manyfold.cluster import ClusterConfig, MemberConfig

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from heart.runtime.manyfold_node import topic_policy_manifest

SCHEMA_VERSION = 1
REQUIRED_ROLE_KINDS = (
    "coordinator",
    "navigation_input_ingress",
    "low_rate_sensor_ingress",
    "renderer",
    "audio_processor",
    "pixel_sink",
)
API_GAPS = (
    "ManyFold LIVE_LATEST replacement identity omits origin_node_id, so "
    "different nodes publishing the same stable source key overwrite each "
    "other in a downstream latest store.",
    "ManyFold bound PubSub rows do not expose origin_node_id, so Heart cannot "
    "observe the required origin/topic/source coalescing identity through the "
    "public consumer surface.",
    "ManyFold LIVE_LATEST exposes no typed coalesce/resync/pressure lifecycle "
    "events or public counters, so Heart cannot prove frame/audio pressure and "
    "recovery without private transport state.",
    "ManyFold StateMachine commit 3c62dd1 is not based on durable-topic commit "
    "ac608640, so Heart cannot pin one exact upstream commit for both APIs.",
)
_ROLE_SPECS = (
    ("coordinator-1", "coordinator", "coordinator-1"),
    ("coordinator-2", "coordinator", "coordinator-2"),
    ("coordinator-3", "coordinator", "coordinator-3"),
    ("navigation-primary", "navigation_input_ingress", "navigation-primary"),
    ("navigation-secondary", "navigation_input_ingress", "navigation-secondary"),
    ("sensor-primary", "low_rate_sensor_ingress", "sensor-primary"),
    ("renderer-primary", "renderer", "renderer-primary"),
    ("audio-primary", "audio_processor", "audio-primary"),
    ("pixel-primary", "pixel_sink", "pixel-primary"),
)


@final
class HeartQualificationSupervisor:
    """Own process topology while the ManyFold gate owns every scenario."""

    def __init__(self) -> None:
        candidate = os.environ.get("MANYFOLD_QUALIFICATION_CANDIDATE_PYTHON", "")
        if not candidate:
            candidate = sys.executable
        self._candidate_python = Path(candidate).absolute()
        self._roles: dict[str, _RoleProcess] = {}
        self._role_start_payloads: dict[str, dict[str, object]] = {}
        self._generation: dict[str, int] = {}
        self._deadline_seconds = 10.0
        self._started = False

    def handle(
        self, operation: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        if operation == "describe":
            return self.describe()
        if operation == "start":
            return self.start(payload)
        if operation == "stimulus":
            return self.stimulus(payload)
        if operation == "observe":
            return self.observe()
        if operation == "restart_role":
            return self.restart_role(_text(payload, "role_id"))
        if operation == "graceful_leave":
            return self.graceful_leave(_text(payload, "role_id"))
        if operation == "close":
            return self.close()
        raise ValueError(f"unknown fixture operation {operation!r}")

    def describe(self) -> dict[str, object]:
        contracts = [
            {
                **contract,
                "retains_journal_rows": (
                    contract["delivery_class"] != "volatile_latest"
                ),
            }
            for contract in topic_policy_manifest()
        ]
        contracts.extend(
            (
                {
                    "topic": "heart.world.mode",
                    "data_class": "ActiveMode",
                    "delivery_class": "raft_state",
                    "coalescing_key": None,
                    "ttl_ms": None,
                    "max_items": None,
                    "max_bytes": None,
                    "max_message_bytes": None,
                    "raft": True,
                    "retains_journal_rows": True,
                },
                {
                    "topic": "heart.world.device",
                    "data_class": "WorldDevice",
                    "delivery_class": "raft_state",
                    "coalescing_key": None,
                    "ttl_ms": None,
                    "max_items": None,
                    "max_bytes": None,
                    "max_message_bytes": None,
                    "raft": True,
                    "retains_journal_rows": True,
                },
            )
        )
        return {
            "consumer": "heart",
            "candidate": _candidate_provenance(self._candidate_python),
            "roles": [
                {
                    "role_id": role_id,
                    "role_kind": role_kind,
                    "node_id": node_id,
                }
                for role_id, role_kind, node_id in _ROLE_SPECS
            ],
            "topic_contracts": contracts,
            "capabilities": [
                "public_lifecycle_batches",
                "public_topic_diagnostics",
                "real_process_roles",
                "role_restart",
                "graceful_leave",
                "persistent_raft_world_state",
                "ring_single_role_failure_tolerance",
            ],
            "api_gaps": list(API_GAPS),
        }

    def start(self, payload: Mapping[str, object]) -> dict[str, object]:
        if self._started:
            raise RuntimeError("qualification roles are already started")
        deadline_ms = payload.get("deadline_ms", 10_000)
        if isinstance(deadline_ms, bool) or not isinstance(deadline_ms, int):
            raise ValueError("deadline_ms must be an integer")
        self._deadline_seconds = max(1.0, deadline_ms / 1000)
        roles = _object_list(payload, "roles")
        expected = {role_id for role_id, _, _ in _ROLE_SPECS}
        observed = {_text(role, "role_id") for role in roles}
        if observed != expected:
            raise ValueError("start roles do not match describe roles")

        role_by_id = {_text(role, "role_id"): role for role in roles}
        listener_ports = {role_id: _unused_port() for role_id, _, _ in _ROLE_SPECS}
        coordinator_config, coordinator_states = _coordinator_config(payload)
        ordered_ids = [role_id for role_id, _, _ in _ROLE_SPECS]
        for index, (role_id, role_kind, node_id) in enumerate(_ROLE_SPECS):
            previous_role_id = ordered_ids[(index - 1) % len(ordered_ids)]
            next_role_id = ordered_ids[(index + 1) % len(ordered_ids)]
            previous_node_id = _node_id(previous_role_id)
            next_node_id = _node_id(next_role_id)
            role = role_by_id[role_id]
            start_payload: dict[str, object] = {
                "role_id": role_id,
                "role_kind": role_kind,
                "node_id": node_id,
                "cluster_id": "qualification",
                "instance_id": f"{role_id}:1",
                "state_directory": _text(role, "state_directory"),
                "journal_directory": _text(role, "journal_directory"),
                "listener": {
                    "peer_node_id": previous_node_id,
                    "port": listener_ports[role_id],
                },
                "connector": {
                    "peer_node_id": next_node_id,
                    "port": listener_ports[next_role_id],
                },
            }
            if role_kind == "coordinator":
                start_payload["coordinator"] = {
                    "config": coordinator_config.to_dict(),
                    "state_directory": str(coordinator_states[node_id]),
                }
            self._role_start_payloads[role_id] = start_payload
            self._generation[role_id] = 1

        try:
            for role_id in ordered_ids:
                self._roles[role_id] = self._spawn_role(
                    role_id,
                    self._role_start_payloads[role_id],
                )
            self._wait_ready()
            self._bootstrap_world()
        except Exception:
            self.close()
            raise
        self._started = True
        return {
            "ready": True,
            "roles": [self._role_handle(role_id) for role_id in ordered_ids],
            "api_gaps": list(API_GAPS),
        }

    def stimulus(self, payload: Mapping[str, object]) -> dict[str, object]:
        role_id = _text(payload, "target_role")
        kind = _text(payload, "kind")
        if kind in {"world_write", "device_write"}:
            role = self._raft_leader()
        else:
            role = self._require_running_role(role_id)
        return role.request("stimulus", payload, timeout=self._deadline_seconds)

    def observe(self) -> dict[str, object]:
        roles: list[dict[str, object]] = []
        operations: list[dict[str, object]] = []
        effects: list[dict[str, object]] = []
        batches: list[dict[str, object]] = []
        diagnostics: list[dict[str, object]] = []
        for role_id, _, _ in _ROLE_SPECS:
            role = self._roles.get(role_id)
            if role is None or not role.is_running:
                roles.append(
                    {
                        "role_id": role_id,
                        "serving": False,
                        "lifecycle_after_sequence": 0,
                        "state_revision": 0,
                        "state_digest": "",
                        "stale_age_ms": None,
                        "sensor_status": "offline",
                        "queue_depth": 0,
                    }
                )
                continue
            observation = role.request(
                "observe",
                {},
                timeout=self._deadline_seconds,
            )
            roles.append(dict(_mapping(observation.get("role"), "role")))
            operations.extend(_object_list(observation, "operations"))
            effects.extend(_object_list(observation, "user_effects"))
            batches.append(dict(_mapping(observation.get("lifecycle_batch"), "batch")))
            for item in _object_list(observation, "topic_diagnostics"):
                diagnostics.append({"role_id": role_id, **item})
        return {
            "roles": roles,
            "operations": _deduplicate_operations(operations),
            "user_effects": effects,
            "lifecycle_batches": batches,
            "topic_diagnostics": diagnostics,
            "api_gaps": list(API_GAPS),
        }

    def restart_role(self, role_id: str) -> dict[str, object]:
        role = self._roles.get(role_id)
        if role is not None:
            role.stop()
        generation = self._generation.get(role_id, 1) + 1
        self._generation[role_id] = generation
        payload = dict(self._role_start_payloads[role_id])
        payload["instance_id"] = f"{role_id}:{generation}"
        restarted = self._spawn_role(role_id, payload)
        self._roles[role_id] = restarted
        self._wait_role_ready(restarted)
        return self._role_handle(role_id)

    def graceful_leave(self, role_id: str) -> dict[str, object]:
        role = self._roles.get(role_id)
        if role is None:
            return {"role_id": role_id, "left": True, "exited": True}
        result = role.close(timeout=self._deadline_seconds)
        return {
            "role_id": role_id,
            "left": True,
            "exited": result.get("exited") is True,
            "lifecycle_batch": result.get("lifecycle_batch"),
        }

    def close(self) -> dict[str, object]:
        roles: list[dict[str, object]] = []
        batches: list[dict[str, object]] = []
        clean = True
        for role_id, _, _ in reversed(_ROLE_SPECS):
            role = self._roles.get(role_id)
            if role is None:
                roles.append({"role_id": role_id, "exited": True})
                continue
            try:
                result = role.close(timeout=min(5.0, self._deadline_seconds))
            except Exception:
                role.stop()
                clean = False
                result = {"exited": not role.is_running}
            roles.append(
                {
                    "role_id": role_id,
                    "exited": result.get("exited") is True,
                    "lifecycle_after_sequence": _batch_after(
                        result.get("lifecycle_batch")
                    ),
                }
            )
            batch = result.get("lifecycle_batch")
            if isinstance(batch, dict):
                batches.append(dict(batch))
        self._roles.clear()
        self._started = False
        return {
            "clean": clean and all(role["exited"] for role in roles),
            "roles": list(reversed(roles)),
            "lifecycle_batches": list(reversed(batches)),
            "api_gaps": list(API_GAPS),
        }

    def _spawn_role(
        self,
        role_id: str,
        payload: Mapping[str, object],
    ) -> "_RoleProcess":
        role = _RoleProcess(
            role_id,
            self._candidate_python,
        )
        try:
            role.request("start", payload, timeout=self._deadline_seconds)
        except Exception:
            role.stop()
            raise
        return role

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + self._deadline_seconds
        pending = set(self._roles)
        stable_samples = {role_id: 0 for role_id in pending}
        while pending and time.monotonic() < deadline:
            for role_id in tuple(pending):
                role = self._roles[role_id]
                if not role.is_running:
                    raise RuntimeError(f"Heart role {role_id!r} exited during startup")
                ready = role.request("ready", {}, timeout=1.0)
                if ready.get("ready") is True:
                    stable_samples[role_id] += 1
                    if stable_samples[role_id] >= 3:
                        pending.remove(role_id)
                else:
                    stable_samples[role_id] = 0
            if pending:
                time.sleep(0.05)
        if pending:
            raise TimeoutError(f"Heart roles did not become ready: {sorted(pending)!r}")

    def _wait_role_ready(self, role: "_RoleProcess") -> None:
        deadline = time.monotonic() + self._deadline_seconds
        stable_samples = 0
        while time.monotonic() < deadline:
            if role.request("ready", {}, timeout=1.0).get("ready") is True:
                stable_samples += 1
                if stable_samples >= 3:
                    return
            else:
                stable_samples = 0
            time.sleep(0.05)
        raise TimeoutError(f"Heart role {role.role_id!r} did not restart")

    def _raft_leader(self) -> "_RoleProcess":
        deadline = time.monotonic() + self._deadline_seconds
        while time.monotonic() < deadline:
            for role_id, role_kind, _ in _ROLE_SPECS:
                if role_kind != "coordinator":
                    continue
                role = self._roles.get(role_id)
                if role is None or not role.is_running:
                    continue
                try:
                    value = role.request("coordinator_status", {}, timeout=1.0)
                except (RuntimeError, TimeoutError):
                    continue
                status = value.get("status")
                if isinstance(status, dict) and status.get("role") == "leader":
                    return role
            time.sleep(0.05)
        raise TimeoutError("Heart coordinator roles did not expose a Raft leader")

    def _bootstrap_world(self) -> None:
        self._raft_leader().request(
            "bootstrap_world",
            {},
            timeout=self._deadline_seconds,
        )

    def _require_running_role(self, role_id: str) -> "_RoleProcess":
        role = self._roles.get(role_id)
        if role is None or not role.is_running:
            raise RuntimeError(f"Heart role {role_id!r} is not serving")
        return role

    def _role_handle(self, role_id: str) -> dict[str, object]:
        role = self._require_running_role(role_id)
        payload = self._role_start_payloads[role_id]
        return {
            "role_id": role_id,
            "process_id": role.process_id,
            "node_id": _text(payload, "node_id"),
            "state_directory": _text(payload, "state_directory"),
            "journal_directory": _text(payload, "journal_directory"),
            "lifecycle_after_sequence": 0,
        }


@final
class _RoleProcess:
    def __init__(self, role_id: str, candidate_python: Path) -> None:
        self.role_id = role_id
        self._next_request_id = 1
        self._process = subprocess.Popen(
            (
                str(candidate_python),
                "-m",
                "heart.runtime._manyfold_qualification_role",
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=_role_environment(),
        )

    @property
    def process_id(self) -> int:
        return self._process.pid

    @property
    def is_running(self) -> bool:
        return self._process.poll() is None

    def request(
        self,
        operation: str,
        payload: Mapping[str, object],
        *,
        timeout: float,
    ) -> dict[str, object]:
        request_id = self._next_request_id
        self._next_request_id += 1
        stdin = self._require_stream(self._process.stdin, "stdin")
        stdout = self._require_stream(self._process.stdout, "stdout")
        stdin.write(
            json.dumps(
                {
                    "request_id": request_id,
                    "operation": operation,
                    "payload": dict(payload),
                },
                sort_keys=True,
            )
            + "\n"
        )
        stdin.flush()
        selector = selectors.DefaultSelector()
        selector.register(stdout, selectors.EVENT_READ)
        try:
            if not selector.select(timeout):
                raise TimeoutError(
                    f"Heart role {self.role_id!r} timed out during {operation}"
                )
            line = stdout.readline()
        finally:
            selector.close()
        if not line:
            raise RuntimeError(
                f"Heart role {self.role_id!r} exited during {operation}: "
                f"{self._stderr()}"
            )
        response = _mapping(json.loads(line), "role response")
        if response.get("request_id") != request_id:
            raise RuntimeError("Heart role response request_id mismatch")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"Heart role {self.role_id!r} {operation} failed: "
                f"{response.get('error')!r}"
            )
        return dict(_mapping(response.get("value"), "role response value"))

    def close(self, *, timeout: float) -> dict[str, object]:
        if not self.is_running:
            return {"exited": True}
        result = self.request("close", {}, timeout=timeout)
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.stop()
            result["exited"] = False
        return result

    def stop(self) -> None:
        if self.is_running:
            self._process.terminate()
            try:
                self._process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1.0)
        for stream in (
            self._process.stdin,
            self._process.stdout,
            self._process.stderr,
        ):
            if stream is not None and not stream.closed:
                stream.close()

    def _stderr(self) -> str:
        stderr = self._process.stderr
        if stderr is None or self.is_running:
            return ""
        return stderr.read().strip()

    @staticmethod
    def _require_stream(stream: IO[str] | None, name: str) -> IO[str]:
        if stream is None:
            raise RuntimeError(f"Heart role {name} pipe is unavailable")
        return stream


def main() -> None:
    """Serve versioned JSONL requests until the gate closes the fixture."""
    supervisor = HeartQualificationSupervisor()
    for line in sys.stdin:
        request_id: object = None
        should_exit = False
        try:
            request = _mapping(json.loads(line), "fixture request")
            request_id = request.get("request_id")
            if request.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
            operation = _text(request, "operation")
            payload = _mapping(request.get("payload", {}), "payload")
            value = supervisor.handle(operation, payload)
            should_exit = operation == "close"
            response = {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "ok": True,
                "value": value,
            }
        except Exception as error:
            response = {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "ok": False,
                "error": {
                    "type": type(error).__name__,
                    "message": str(error),
                    "api_gaps": list(API_GAPS),
                },
            }
        sys.stdout.write(json.dumps(response, sort_keys=True) + "\n")
        sys.stdout.flush()
        if should_exit:
            return


def _candidate_provenance(candidate_python: Path) -> dict[str, object]:
    installed = distribution("manyfold")
    direct_url_text = installed.read_text("direct_url.json")
    direct_url = json.loads(direct_url_text) if direct_url_text is not None else None
    if direct_url is not None and not isinstance(direct_url, dict):
        raise ValueError("manyfold direct_url.json must contain an object")
    return {
        "python_executable": str(candidate_python),
        "manyfold_version": installed.version,
        "direct_url": direct_url,
        "wheel_sha256": _wheel_sha256(direct_url),
    }


def _wheel_sha256(direct_url: object) -> str:
    if not isinstance(direct_url, dict):
        return ""
    archive = direct_url.get("archive_info")
    if isinstance(archive, dict):
        hashes = archive.get("hashes")
        if isinstance(hashes, dict) and isinstance(hashes.get("sha256"), str):
            digest = hashes["sha256"]
            return str(digest)
        value = archive.get("hash")
        if isinstance(value, str) and value.startswith("sha256="):
            return value.removeprefix("sha256=")
    url = direct_url.get("url")
    if not isinstance(url, str):
        return ""
    parsed = urlparse(url)
    if parsed.scheme != "file" or not parsed.path.endswith(".whl"):
        return ""
    wheel = Path(unquote(parsed.path))
    if not wheel.is_file():
        return ""
    digest = hashlib.sha256()
    with wheel.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _coordinator_config(
    payload: Mapping[str, object],
) -> tuple[ClusterConfig, dict[str, Path]]:
    coordinator = _mapping(payload.get("coordinator"), "coordinator")
    supplied_members = _object_list(coordinator, "members")
    if len(supplied_members) != 3:
        raise ValueError("Heart qualification requires three coordinator members")
    members: list[MemberConfig] = []
    states: dict[str, Path] = {}
    api_ports: set[int] = set()
    for supplied in supplied_members:
        node_id = _text(supplied, "node_id")
        raft_port = _integer(supplied, "port")
        api_port = _unused_port()
        while api_port == raft_port or api_port in api_ports:
            api_port = _unused_port()
        api_ports.add(api_port)
        members.append(
            MemberConfig(node_id, _text(supplied, "host"), raft_port, api_port)
        )
        states[node_id] = Path(_text(supplied, "state_directory"))
    return ClusterConfig(tuple(members)), states


def _deduplicate_operations(
    operations: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_id: dict[str, dict[str, object]] = {}
    for operation in operations:
        operation_id = _text(operation, "operation_id")
        existing = by_id.get(operation_id)
        if existing is None:
            by_id[operation_id] = dict(operation)
            continue
        existing["apply_count"] = max(
            _non_negative_integer(existing.get("apply_count"), "apply_count"),
            _non_negative_integer(operation.get("apply_count"), "apply_count"),
        )
        if existing.get("status") != "applied" and operation.get("status") == "applied":
            existing["status"] = "applied"
    return [by_id[key] for key in sorted(by_id)]


def _role_environment() -> dict[str, str]:
    environment: dict[str, str] = {
        "PYTHONUNBUFFERED": "1",
        "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        "HEART_PI5_MATRIX_BACKEND": "simulated",
    }
    for name in ("PATH", "LANG", "LC_ALL", "TMPDIR"):
        value = os.environ.get(name)
        if value is not None:
            environment[name] = value
    return environment


def _node_id(role_id: str) -> str:
    for candidate_role_id, _, node_id in _ROLE_SPECS:
        if candidate_role_id == role_id:
            return node_id
    raise ValueError(f"unknown role_id {role_id!r}")


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as value:
        value.bind(("127.0.0.1", 0))
        return int(value.getsockname()[1])


def _batch_after(value: object) -> int:
    if not isinstance(value, dict):
        return 0
    after = value.get("cursor_after")
    return after if isinstance(after, int) else 0


def _object_list(
    value: Mapping[str, object],
    name: str,
) -> list[dict[str, object]]:
    items = value.get(name)
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise ValueError(f"{name} must be a list of objects")
    return items


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object")
    return value


def _text(value: Mapping[str, object], name: str) -> str:
    item = value.get(name)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return item


def _integer(value: Mapping[str, object], name: str) -> int:
    item = value.get(name)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{name} must be an integer")
    return item


def _non_negative_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


if __name__ == "__main__":
    main()
