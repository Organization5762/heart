"""Compatibility wrapper for sensor metric aggregation tests.

Pytest now collects the dedicated modules under :mod:`tests.events.metrics`.
This module remains so existing imports continue to resolve without change.
"""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Final

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_METRIC_MODULES: Final[tuple[str, ...]] = (
    "tests.events.metrics.test_count_by_key",
    "tests.events.metrics.test_event_window_policies",
    "tests.events.metrics.test_last_event_windows",
    "tests.events.metrics.test_rolling_statistics_by_key",
)

for module_name in _METRIC_MODULES:
    import_module(module_name)
