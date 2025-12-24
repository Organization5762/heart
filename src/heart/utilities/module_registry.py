from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TypeVar

from heart.utilities.logging import get_logger

T = TypeVar("T")

logger = get_logger(__name__)


def discover_registry(
    configurations_dir: Path,
    module_root: str,
    attribute: str = "configure",
    *,
    log_imports: bool = False,
) -> dict[str, T]:
    registry: dict[str, T] = {}
    for entry in configurations_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix != ".py" or entry.name == "__init__.py":
            continue
        module_name = f"{module_root}.{entry.stem}"
        module = import_module(module_name)
        if log_imports:
            logger.info("Importing configuration: %s", module_name)
        if hasattr(module, attribute):
            registry[entry.stem] = getattr(module, attribute)
    return registry
