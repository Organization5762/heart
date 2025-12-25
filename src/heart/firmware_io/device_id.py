"""Helpers for persisting and resolving device identifiers."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType
from typing import Callable, Mapping, TextIO

DEVICE_ID_ENV_VAR = "HEART_DEVICE_ID"
DEVICE_ID_PATH_ENV_VAR = "HEART_DEVICE_ID_PATH"
DEFAULT_DEVICE_ID_FILENAME = "device_id.txt"
DEFAULT_DEVICE_ID_PATH = Path("/") / DEFAULT_DEVICE_ID_FILENAME


def default_device_id_path(env: Mapping[str, str] | None = None) -> Path:
    """Return the filesystem path used to persist device identifiers."""

    env_mapping = env or os.environ
    configured = env_mapping.get(DEVICE_ID_PATH_ENV_VAR)
    if configured:
        return Path(configured)
    return DEFAULT_DEVICE_ID_PATH


def persistent_device_id(
    *,
    storage_path: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    opener: Callable[[str | Path, str], TextIO] | None = None,
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
    path = Path(storage_path) if storage_path else default_device_id_path(env_mapping)
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


def _hardware_device_uid(microcontroller_module: ModuleType | None = None) -> str | None:
    module = microcontroller_module
    if module is None:
        if importlib.util.find_spec("microcontroller") is None:  # pragma: no cover - hardware only
            return None
        module = importlib.import_module("microcontroller")

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
    path: Path | None,
    opener: Callable[[str | Path, str], TextIO],
) -> str | None:
    if not path:
        return None

    try:
        with opener(path, "r") as handle:
            raw = handle.read().strip()
    except OSError:
        return None

    return raw or None


def _write_device_id(path: Path, value: str, opener: Callable[[str | Path, str], TextIO]) -> None:
    _ensure_directory(path.parent)

    try:
        with opener(path, "w") as handle:
            handle.write(value)
    except OSError:
        return


def _ensure_directory(path: Path) -> None:
    if path in (Path("."), Path("/")):
        return

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
