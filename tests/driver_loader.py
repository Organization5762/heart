
import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Dict


@contextmanager
def temporary_modules(stubs: Dict[str, ModuleType]):
    previous: dict[str, ModuleType | None] = {}
    try:
        for name, module in stubs.items():
            previous[name] = sys.modules.get(name)
            sys.modules[name] = module
        yield
    finally:
        for name, module in stubs.items():
            original = previous.get(name)
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def make_module(name: str, **attributes) -> ModuleType:
    module = ModuleType(name)
    for attr, value in attributes.items():
        setattr(module, attr, value)
    return module


def load_driver_module(module_dir: str, *, stubs: Dict[str, ModuleType] | None = None):
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "drivers" / module_dir / "code.py"
    spec = importlib.util.spec_from_file_location(
        f"drivers_{module_dir.replace('-', '_')}_code", module_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load driver module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module.__name__] = module
    with temporary_modules(stubs or {}):
        spec.loader.exec_module(module)
    return module