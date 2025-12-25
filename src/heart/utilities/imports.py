from __future__ import annotations

from importlib import import_module, util
from types import ModuleType

from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def module_available(module_name: str) -> bool:
    """Return whether a module can be imported in this runtime."""

    try:
        return util.find_spec(module_name) is not None
    except Exception as exc:  # pragma: no cover - defensive: invalid specs/platform quirks
        logger.debug("Failed to check module availability for %s: %s", module_name, exc)
        return False


def optional_import(module_name: str) -> ModuleType | None:
    """Import an optional dependency, returning ``None`` when unavailable."""

    if not module_available(module_name):
        return None
    try:
        return import_module(module_name)
    except Exception as exc:  # pragma: no cover - optional dependencies may fail at import time
        logger.debug("Optional dependency %s failed to import: %s", module_name, exc)
        return None
