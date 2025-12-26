from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PeripheralConfigurationLoader:
    """Load and cache peripheral configurations by name."""

    def __init__(
        self,
        *,
        configuration: str | None = None,
        registry: PeripheralConfigurationRegistry | None = None,
    ) -> None:
        self._registry = registry or PeripheralConfigurationRegistry()
        self._configuration_name = (
            configuration or Configuration.peripheral_configuration()
        )
        self._configuration: PeripheralConfiguration | None = None

    @property
    def name(self) -> str:
        return self._configuration_name

    @property
    def registry(self) -> PeripheralConfigurationRegistry:
        return self._registry

    def load(self) -> PeripheralConfiguration:
        if self._configuration is None:
            self._configuration = self._load_configuration(self._configuration_name)
        return self._configuration

    def _load_configuration(self, name: str) -> PeripheralConfiguration:
        factory = self._registry.get(name)
        if factory is None:
            raise ValueError(f"Peripheral configuration '{name}' not found")
        logger.info("Loading peripheral configuration: %s", name)
        return factory()
