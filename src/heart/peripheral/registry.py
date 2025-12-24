"""Registry for peripheral detection configurations."""

from __future__ import annotations

import importlib
from functools import cached_property
from pathlib import Path
from typing import Callable

from heart.peripheral.configuration import PeripheralConfiguration

ConfigurationFactory = Callable[[], PeripheralConfiguration]


class PeripheralConfigurationRegistry:
    """Discover available peripheral configuration modules."""

    @cached_property
    def registry(self) -> dict[str, ConfigurationFactory]:
        registry: dict[str, ConfigurationFactory] = {}
        configurations_dir = Path(__file__).resolve().parent / "configurations"
        for entry in configurations_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix != ".py" or entry.name == "__init__.py":
                continue
            module_name = f"heart.peripheral.configurations.{entry.stem}"
            module = importlib.import_module(module_name)
            if hasattr(module, "configure"):
                registry[entry.stem] = getattr(module, "configure")
        return registry

    def get(self, name: str) -> ConfigurationFactory | None:
        return self.registry.get(name)
