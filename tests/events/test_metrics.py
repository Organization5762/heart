"""Compatibility wrapper for sensor metric aggregation tests.

Pytest now collects the dedicated modules under :mod:`tests.events.metrics`.
This module remains so existing imports continue to resolve without change.
"""

from __future__ import annotations

from importlib import import_module
from typing import Final

_METRIC_MODULES: Final[tuple[str, ...]] = (
    "tests.events.metrics.test_count_by_key",
    "tests.events.metrics.test_event_window_policies",
    "tests.events.metrics.test_last_event_windows",
    "tests.events.metrics.test_rolling_statistics_by_key",
)

for module_name in _METRIC_MODULES:
    import_module(module_name)

__all__ = ("_METRIC_MODULES",)
