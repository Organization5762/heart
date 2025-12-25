"""Helpers for optional imports."""

from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType

from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def optional_import(module_name: str) -> ModuleType | None:
    """Return the imported module if available, otherwise ``None``."""

    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ModuleNotFoundError) as exc:
        logger.debug("Optional dependency lookup failed for %s: %s", module_name, exc)
        return None

    if spec is None:
        return None

    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        logger.debug("Optional dependency %s failed to import: %s", module_name, exc)
        return None
    except Exception as exc:
        logger.warning("Optional dependency %s failed to initialize: %s", module_name, exc)
        return None
