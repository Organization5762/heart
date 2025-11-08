"""Compatibility wrapper for sensor metric aggregation tests.

Pytest now collects the dedicated modules under :mod:`tests.events.metrics`.
This module remains so existing imports continue to resolve without change.
"""


import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Final

_METRIC_MODULES: Final[tuple[str, ...]] = (
    "test_count_by_key",
    "test_event_window_policies",
    "test_last_event_windows",
    "test_rolling_statistics_by_key",
)


def _ensure_package(name: str, *, path: Path) -> ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
    return module


_ROOT = Path(__file__).resolve().parent
_TESTS_PACKAGE = _ensure_package("tests", path=_ROOT.parent)
_EVENTS_PACKAGE = _ensure_package("tests.events", path=_ROOT)
_METRICS_PACKAGE = _ensure_package("tests.events.metrics", path=_ROOT / "metrics")

setattr(_TESTS_PACKAGE, "events", _EVENTS_PACKAGE)
setattr(_EVENTS_PACKAGE, "metrics", _METRICS_PACKAGE)

pytest_plugins = tuple(f"tests.events.metrics.{name}" for name in _METRIC_MODULES)

for module_name in _METRIC_MODULES:
    module = import_module(f"tests.events.metrics.{module_name}")
    setattr(_METRICS_PACKAGE, module_name, module)
