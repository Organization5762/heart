"""Helpers for importing Rust-backed renderers."""

from __future__ import annotations

import importlib.util
import os
import sys
from importlib import import_module, machinery
from pathlib import Path
from types import ModuleType
from typing import Sequence

from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def import_rust_renderer(
    module_name: str,
    *,
    search_paths: Sequence[Path] | None = None,
) -> ModuleType:
    """Import a Rust-backed renderer module.

    Args:
        module_name: The importable module name (e.g. ``heart.renderers.rust_demo``).
        search_paths: Optional paths to search for extension modules.
    """

    resolved_paths = _resolve_search_paths(search_paths)
    if not resolved_paths:
        return import_module(module_name)

    logger.debug(
        "Searching Rust renderer paths for import: %s",
        ", ".join(str(path) for path in resolved_paths),
    )

    search_roots = [str(path) for path in resolved_paths]
    spec = machinery.PathFinder.find_spec(module_name, search_roots)
    if spec is None:
        raise ModuleNotFoundError(
            f"Rust renderer module '{module_name}' not found in {search_roots}"
        )
    return _load_spec(module_name, spec)


def _resolve_search_paths(search_paths: Sequence[Path] | None) -> list[Path]:
    env_paths = _parse_env_paths(os.environ.get("HEART_RUST_RENDERERS_PATH", ""))
    combined: list[Path] = []
    for path in (*env_paths, *list(search_paths or [])):
        resolved = path.expanduser().resolve()
        if resolved not in combined:
            combined.append(resolved)
    return combined


def _parse_env_paths(raw_paths: str) -> list[Path]:
    if not raw_paths:
        return []
    return [Path(entry) for entry in raw_paths.split(os.pathsep) if entry]


def _load_spec(module_name: str, spec: importlib.machinery.ModuleSpec) -> ModuleType:
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    if spec.loader is None:
        raise ModuleNotFoundError(f"Rust renderer module '{module_name}' has no loader")
    spec.loader.exec_module(module)
    return module
