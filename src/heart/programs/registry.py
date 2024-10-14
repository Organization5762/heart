import importlib
import os

registry = {}

configurations_dir = os.path.dirname(__file__) + "/configurations"
for filename in os.listdir(configurations_dir):
    if filename.endswith(".py") and filename != "__init__.py":
        module_name = f"heart.programs.configurations.{filename[:-3]}"
        module = importlib.import_module(module_name)
        if hasattr(module, "configure"):
            registry[filename[:-3]] = module.configure


def get_from_registry(name: str):
    return registry.get(name)
