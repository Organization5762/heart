"""Helpers for importing Rust-backed renderers."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Iterable, Iterator, Sequence

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
        search_paths: Optional paths to temporarily add to ``sys.path``.
    """

    resolved_paths = _resolve_search_paths(search_paths)
    if resolved_paths:
        logger.debug(
            "Adding Rust renderer search paths for import: %s",
            ", ".join(str(path) for path in resolved_paths),
        )

    with _temporary_sys_path(resolved_paths):
        return import_module(module_name)


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


@contextmanager
def _temporary_sys_path(paths: Iterable[Path]) -> Iterator[None]:
    inserted: list[str] = []
    for path in paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            inserted.append(path_str)
    try:
        yield
    finally:
        for path_str in inserted:
            if path_str in sys.path:
                sys.path.remove(path_str)
