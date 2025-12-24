import importlib
from functools import cached_property
from pathlib import Path
from typing import Callable

from heart.environment import GameLoop
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class ConfigurationRegistry:
    @cached_property
    def registry(self) -> dict[str, Callable[[GameLoop], None]]:
        registry: dict[str, Callable[[GameLoop], None]] = {}
        configurations_dir = Path(__file__).resolve().parent / "configurations"
        for configuration in configurations_dir.iterdir():
            if configuration.suffix == ".py" and configuration.name != "__init__.py":
                module_name = (
                    f"heart.programs.configurations.{configuration.stem}"
                )
                module = importlib.import_module(module_name)
                logger.info("Importing configuration: %s", module_name)
                if hasattr(module, "configure"):
                    registry[configuration.stem] = module.configure

        return registry

    def get(self, name: str) -> Callable[[GameLoop], None] | None:
        return self.registry.get(name)
