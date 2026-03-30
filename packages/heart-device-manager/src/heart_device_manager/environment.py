"""Environment helpers for device manager workflows."""

from __future__ import annotations

import os
import platform

ON_PI_ENV_VAR = "ON_PI"
TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def is_pi() -> bool:
    """Return ``True`` when running on Raspberry Pi-like hosts."""

    return platform.system() == "Linux" or _env_flag(ON_PI_ENV_VAR)


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in TRUTHY_ENV_VALUES
