import importlib
import os
from typing import Callable

from heart.environment import GameLoop


class ConfigurationRegistry:
    def __init__(self) -> None:
        self.registry: dict[str, Callable[[GameLoop], None]] = {}

    def _load_registry(self):
        configurations_dir = os.path.dirname(__file__) + "/configurations"
        for filename in os.listdir(configurations_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = f"heart.programs.configurations.{filename[:-3]}"
                module = importlib.import_module(module_name)
                if hasattr(module, "configure"):
                    self.registry[filename[:-3]] = module.configure

    def get(self, name: str) -> Callable[[GameLoop], None] | None:
        return self.registry.get(name)