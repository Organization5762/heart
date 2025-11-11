"""Path helpers for resolving locations inside the repository."""

from __future__ import annotations

from functools import cache
from os import PathLike
from pathlib import Path
from typing import Iterable

PathInput = str | PathLike[str]


def _build_relative_path(parts: Iterable[PathInput]) -> Path:
    path = Path()
    for part in parts:
        path /= Path(part)
    return path


@cache
def repo_root() -> Path:
    """Return the root directory of the repository."""

    return Path(__file__).resolve().parents[2]


def heart_asset_path(*relative_parts: PathInput) -> Path:
    """Resolve a path inside ``src/heart/assets``."""

    return repo_root() / "src" / "heart" / "assets" / _build_relative_path(relative_parts)


def docs_asset_path(*relative_parts: PathInput) -> Path:
    """Resolve a path inside ``docs/assets``."""

    return repo_root() / "docs" / "assets" / _build_relative_path(relative_parts)
