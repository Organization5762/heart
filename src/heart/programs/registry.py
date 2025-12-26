from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from heart.runtime.game_loop import GameLoop
from heart.utilities.module_registry import discover_registry


class ConfigurationRegistry:
    @cached_property
    def registry(self) -> dict[str, Callable[["GameLoop"], None]]:
        configurations_dir = Path(__file__).resolve().parent / "configurations"
        return discover_registry(
            configurations_dir,
            "heart.programs.configurations",
            attribute="configure",
            log_imports=True,
        )

    def get(self, name: str) -> Callable[["GameLoop"], None] | None:
        return self.registry.get(name)
