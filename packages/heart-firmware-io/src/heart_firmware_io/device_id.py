"""Helpers for persisting and resolving device identifiers."""

from __future__ import annotations

import os

try:
    import microcontroller
except ImportError:  # pragma: no cover - CPython fallback
    microcontroller = None

DEVICE_ID_ENV_VAR = "HEART_DEVICE_ID"
DEVICE_ID_PATH_ENV_VAR = "HEART_DEVICE_ID_PATH"
DEFAULT_DEVICE_ID_FILENAME = "device_id.txt"
DEFAULT_DEVICE_ID_PATH = "/" + DEFAULT_DEVICE_ID_FILENAME


def default_device_id_path(env=None) -> str:
    """Return the filesystem path used to persist device identifiers."""

    env_mapping = env or getattr(os, "environ", {})
    configured = env_mapping.get(DEVICE_ID_PATH_ENV_VAR)
    if configured:
        return configured
    return DEFAULT_DEVICE_ID_PATH


def persistent_device_id(
    *,
    storage_path=None,
    env=None,
    opener=None,
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

    env_mapping = env or getattr(os, "environ", {})
    path = (
        _pathlike_to_string(storage_path)
        if storage_path
        else default_device_id_path(env_mapping)
    )
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


def _hardware_device_uid(microcontroller_module=None) -> str | None:
    module = microcontroller_module or microcontroller
    if module is None:
        return None

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


def _read_device_id(
    path: str | None,
    opener,
) -> str | None:
    if not path:
        return None

    try:
        with opener(path, "r") as handle:
            raw = handle.read().strip()
    except OSError:
        return None

    return raw or None


def _write_device_id(path: str, value: str, opener) -> None:
    _ensure_directory(_parent_directory(path))

    try:
        with opener(path, "w") as handle:
            handle.write(value)
    except OSError:
        return


def _ensure_directory(path: str) -> None:
    if path in ("", ".", "/"):
        return

    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return


def _pathlike_to_string(path) -> str:
    try:
        return os.fspath(path)
    except AttributeError:
        return str(path)


def _parent_directory(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""
