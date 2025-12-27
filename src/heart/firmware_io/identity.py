"""Helpers for responding to identity queries over the serial bus."""

from __future__ import annotations

import importlib
import json
import sys
from types import ModuleType
from typing import Callable, Iterable, Mapping, TextIO

from heart.firmware_io import constants

supervisor: ModuleType | None
if importlib.util.find_spec("supervisor") is not None:  # pragma: no cover - exercised on hardware
    supervisor = importlib.import_module("supervisor")
else:  # pragma: no cover - supervisor is unavailable on CPython
    supervisor = None


_DEFAULT_COMMIT_CACHE: str | None = None
DEFAULT_FIRMWARE_COMMIT = "UNKNOWN"

class Identity:
    """Container describing a firmware build."""

    def __init__(
        self,
        device_name: str,
        firmware_commit: str,
        device_id: str,
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        self.device_name = device_name
        self.firmware_commit = firmware_commit
        self.device_id = device_id
        self._metadata = dict(metadata or {})

    def as_payload(self) -> Mapping[str, str]:
        payload = {
            "device_name": self.device_name,
            "firmware_commit": self.firmware_commit,
            "device_id": self.device_id,
        }
        payload.update(self._metadata)
        return payload


def default_firmware_commit(default: str = DEFAULT_FIRMWARE_COMMIT) -> str:
    """Return a best-effort commit identifier for the running firmware."""

    global _DEFAULT_COMMIT_CACHE
    if _DEFAULT_COMMIT_CACHE is not None:
        return _DEFAULT_COMMIT_CACHE

    commit = _commit_from_generated_module()
    if commit is None:
        commit = _commit_from_git(default)
    if commit is None:
        commit = default

    _DEFAULT_COMMIT_CACHE = commit
    return commit


def poll_and_respond(
    identity: Identity,
    *,
    stdin: TextIO | None = None,
    print_fn: Callable[[str], None] = print,
) -> bool:
    """Respond to any pending serial queries.

    Returns ``True`` if at least one Identify query was processed.
    """

    handled = False
    for query in _iter_serial_queries(stdin=stdin):
        normalized = _extract_command(query)
        if normalized is None:
            continue
        if normalized.lower() == "identify":
            print_fn(_format_identity_payload(identity))
            handled = True
    return handled


def _format_identity_payload(identity: Identity) -> str:
    return json.dumps({"event_type": constants.DEVICE_IDENTIFY, "data": identity.as_payload()})


def _iter_serial_queries(*, stdin: TextIO | None) -> Iterable[str]:
    provided_stream = stdin
    stream = stdin or sys.stdin
    if stream is None:
        return []

    queries = []
    while _serial_bytes_available(stdin_provided=provided_stream is not None):
        try:
            line = stream.readline()
        except OSError:
            break
        if not line:
            break
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="ignore")
        stripped = line.strip()
        if stripped:
            queries.append(stripped)

    return queries


def _serial_bytes_available(*, stdin_provided: bool) -> bool:
    if supervisor is None:
        return stdin_provided

    runtime = getattr(supervisor, "runtime", None)
    if runtime is None:
        return stdin_provided

    available = getattr(runtime, "serial_bytes_available", None)
    if available is None:
        return stdin_provided

    if isinstance(available, int):
        return available > 0

    try:
        return int(available) > 0
    except Exception:  # pragma: no cover - defensive fallback
        return True


def _extract_command(raw: str) -> str | None:
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
    except ValueError:
        return raw

    if isinstance(parsed, Mapping):
        candidate = parsed.get("query") or parsed.get("command")
        if isinstance(candidate, str):
            return candidate

    return raw if isinstance(raw, str) else None


def _commit_from_generated_module() -> str | None:
    if importlib.util.find_spec("heart_firmware_build") is None:
        return None
    module = importlib.import_module("heart_firmware_build")

    commit = getattr(module, "FIRMWARE_COMMIT", None)
    if isinstance(commit, str) and commit:
        return commit
    return None


def _commit_from_git(default: str) -> str | None:
    if importlib.util.find_spec("subprocess") is None:  # pragma: no cover - hardware environments
        return None
    subprocess = importlib.import_module("subprocess")

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:  # pragma: no cover - defensive fallback
        return default

    commit = result.stdout.strip()
    return commit or default
