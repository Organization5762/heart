"""Registry for peripheral detection configurations."""

from __future__ import annotations

import importlib
import os
from functools import cached_property
from typing import Callable

from heart.peripheral.configuration import PeripheralConfiguration

if False:  # pragma: no cover - for type checkers only
    from heart.peripheral.core.manager import PeripheralManager

ConfigurationFactory = Callable[["PeripheralManager"], PeripheralConfiguration]


class PeripheralConfigurationRegistry:
    """Discover available peripheral configuration modules."""

    @cached_property
    def registry(self) -> dict[str, ConfigurationFactory]:
        registry: dict[str, ConfigurationFactory] = {}
        configurations_dir = os.path.join(os.path.dirname(__file__), "configurations")
        for filename in os.listdir(configurations_dir):
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            module_name = f"heart.peripheral.configurations.{filename[:-3]}"
            module = importlib.import_module(module_name)
            if hasattr(module, "configure"):
                registry[filename[:-3]] = getattr(module, "configure")
        return registry

    def get(self, name: str) -> ConfigurationFactory | None:
        return self.registry.get(name)
