"""Registry for peripheral detection configurations."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Callable

from heart.peripheral.configuration import PeripheralConfiguration
from heart.utilities.module_registry import discover_registry

ConfigurationFactory = Callable[[], PeripheralConfiguration]


class PeripheralConfigurationRegistry:
    """Discover available peripheral configuration modules."""

    @cached_property
    def registry(self) -> dict[str, ConfigurationFactory]:
        configurations_dir = Path(__file__).resolve().parent / "configurations"
        return discover_registry(
            configurations_dir,
            "heart.peripheral.configurations",
            attribute="configure",
        )

    def get(self, name: str) -> ConfigurationFactory | None:
        return self.registry.get(name)
