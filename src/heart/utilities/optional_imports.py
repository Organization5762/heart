"""Helpers for optional dependency imports."""

from __future__ import annotations

import importlib
import importlib.util
from logging import Logger
from typing import Any

from heart.utilities.logging import get_logger


def optional_import(
    module_name: str,
    *,
    logger: Logger | None = None,
) -> Any | None:
    """Return the imported module if available, otherwise ``None``."""

    resolved_logger = logger or get_logger(__name__)

    try:
        if importlib.util.find_spec(module_name) is None:
            resolved_logger.debug("Optional dependency %s is unavailable.", module_name)
            return None
    except Exception as exc:
        resolved_logger.debug(
            "Optional dependency lookup failed for %s: %s", module_name, exc
        )
        return None

    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        resolved_logger.warning(
            "Optional dependency %s failed to import: %s", module_name, exc
        )
        return None


def optional_import_attribute(
    module_name: str,
    attribute: str,
    *,
    logger: Logger | None = None,
) -> Any | None:
    """Return ``attribute`` from ``module_name`` if available, otherwise ``None``."""

    resolved_logger = logger or get_logger(__name__)
    module = optional_import(module_name, logger=resolved_logger)
    if module is None:
        return None
    try:
        return getattr(module, attribute)
    except AttributeError:
        resolved_logger.warning(
            "Optional dependency %s is missing attribute %s.", module_name, attribute
        )
        return None
