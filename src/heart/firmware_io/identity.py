"""Helpers for responding to identity queries over the serial bus."""


import json
import os
import sys
from typing import Callable, Iterable, Mapping, TextIO

from heart.firmware_io import constants

try:  # pragma: no cover - supervisor is unavailable on CPython
    import supervisor  # type: ignore
except ImportError:  # pragma: no cover - exercised on hardware
    supervisor = None  # type: ignore


_DEFAULT_COMMIT_CACHE: str | None = None

DEVICE_ID_ENV_VAR = "HEART_DEVICE_ID"
DEVICE_ID_PATH_ENV_VAR = "HEART_DEVICE_ID_PATH"
DEFAULT_DEVICE_ID_FILENAME = "device_id.txt"
DEFAULT_DEVICE_ID_PATH = f"/{DEFAULT_DEVICE_ID_FILENAME}"


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


def default_firmware_commit(default: str = "UNKNOWN") -> str:
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


def default_device_id_path(env: Mapping[str, str] | None = None) -> str:
    """Return the filesystem path used to persist device identifiers."""

    env_mapping = env or os.environ
    return env_mapping.get(DEVICE_ID_PATH_ENV_VAR, DEFAULT_DEVICE_ID_PATH)


def persistent_device_id(
    *,
    storage_path: str | None = None,
    env: Mapping[str, str] | None = None,
    opener: Callable[[str, str], TextIO] | None = None,
    microcontroller_module=None,
) -> str:
    """Return a device identifier that remains stable across boots.

    The identifier is sourced in the following priority order:

    1. ``storage_path`` contents if the file exists.
    2. ``DEVICE_ID_ENV_VAR`` (``HEART_DEVICE_ID``) environment variable.
    3. The hardware UID exposed by ``microcontroller.cpu.uid``.
    4. A randomly generated hexadecimal token.

    When a non-file source is used, the identifier is written back to
    ``storage_path`` so subsequent boots re-use the same value without
    requiring the environment variable.
    """

    env_mapping = env or os.environ
    path = storage_path or default_device_id_path(env_mapping)
    opener_fn = opener or open

    existing = _read_device_id(path, opener_fn)
    if existing:
        return existing

    candidate = None
    if env_mapping is not None:
        candidate = env_mapping.get(DEVICE_ID_ENV_VAR)
    if not candidate:
        candidate = _hardware_device_uid(microcontroller_module)
    if not candidate:
        candidate = _random_device_id()

    if candidate and path:
        _write_device_id(path, candidate, opener_fn)

    return candidate


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
    try:
        from heart_firmware_build import FIRMWARE_COMMIT  # type: ignore

        if isinstance(FIRMWARE_COMMIT, str) and FIRMWARE_COMMIT:
            return FIRMWARE_COMMIT
    except ImportError:
        return None
    return None


def _commit_from_git(default: str) -> str | None:
    try:
        import subprocess
    except (ImportError, NotImplementedError):  # pragma: no cover - hardware environments
        return None

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


def _hardware_device_uid(microcontroller_module=None) -> str | None:
    module = microcontroller_module
    if module is None:
        try:  # pragma: no cover - available on CircuitPython only
            import microcontroller  # type: ignore
        except ImportError:
            return None
        module = microcontroller  # type: ignore

    cpu = getattr(module, "cpu", None)
    uid = getattr(cpu, "uid", None) if cpu is not None else None
    if uid is None:
        return None

    if isinstance(uid, bytes):
        return uid.hex()

    if isinstance(uid, str):
        return uid

    try:
        return bytes(uid).hex()
    except Exception:  # pragma: no cover - defensive fallback
        return None


def _random_device_id() -> str:
    try:
        random_bytes = os.urandom(8)
    except (AttributeError, NotImplementedError):  # pragma: no cover - hardware fallback
        random_bytes = b"\x00" * 8
    return random_bytes.hex()


def _read_device_id(path: str | None, opener: Callable[[str, str], TextIO]) -> str | None:
    if not path:
        return None

    try:
        with opener(path, "r") as handle:
            raw = handle.read().strip()
    except OSError:
        return None

    return raw or None


def _write_device_id(path: str, value: str, opener: Callable[[str, str], TextIO]) -> None:
    parent = _parent_directory(path)
    if parent:
        _ensure_directory(parent)

    try:
        with opener(path, "w") as handle:
            handle.write(value)
    except OSError:
        return


def _parent_directory(path: str) -> str:
    if not path or "/" not in path:
        return ""

    directory, _ = path.rsplit("/", 1)
    return directory or "/"


def _ensure_directory(path: str) -> None:
    if not path or path == "/":
        return

    try:
        os.makedirs(path)  # type: ignore[attr-defined]
        return
    except AttributeError:
        pass
    except OSError:
        return

    try:
        os.mkdir(path)
    except OSError:
        return