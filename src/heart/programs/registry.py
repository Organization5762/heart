import importlib
import os
from functools import cached_property
from typing import Callable

from heart.environment import GameLoop


class ConfigurationRegistry:
    @cached_property
    def registry(self) -> dict[str, Callable[[GameLoop], None]]:
        registry: dict[str, Callable[[GameLoop], None]] = {}
        configurations_dir = os.path.join(os.path.dirname(__file__), "configurations")
        for filename in os.listdir(configurations_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = f"heart.programs.configurations.{filename[:-3]}"
                module = importlib.import_module(module_name)
                print(f"Importing configuration: {module_name}")
                if hasattr(module, "configure"):
                    registry[filename[:-3]] = module.configure

        return registry

    def get(self, name: str) -> Callable[[GameLoop], None] | None:
        return self.registry.get(name)
