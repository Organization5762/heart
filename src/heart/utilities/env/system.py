import os
import platform
import re
from dataclasses import dataclass
from functools import cache

from heart.utilities.env.parsing import _env_flag


@dataclass
class Pi:
    version: int


class SystemConfiguration:
    @classmethod
    @cache
    def is_pi(cls) -> bool:
        return platform.system() == "Linux" or _env_flag("ON_PI")

    @classmethod
    def pi(cls) -> Pi | None:
        if not cls.is_pi():
            return None

        with open("/proc/device-tree/model", "rb") as fp:
            raw = fp.read()
            model = raw.decode("ascii", errors="ignore").rstrip("\x00\n")

            # Match “Raspberry Pi X” and capture X
            match = re.search(r"Raspberry Pi (\d+)", model)
            if not match:
                raise ValueError(f"Couldn't parse Pi model from {model!r}")
            return Pi(version=int(match.group(1)))

    @classmethod
    def is_profiling_mode(cls) -> bool:
        return _env_flag("PROFILING_MODE")

    @classmethod
    def is_debug_mode(cls) -> bool:
        return _env_flag("DEBUG_MODE")

    @classmethod
    def is_x11_forward(cls) -> bool:
        return _env_flag("X11_FORWARD")

    @classmethod
    def use_mock_switch(cls) -> bool:
        return _env_flag("MOCK_SWITCH")

    @classmethod
    def use_isolated_renderer(cls) -> bool:
        return _env_flag("USE_ISOLATED_RENDERER")

    @classmethod
    def forward_to_beats_app(cls) -> bool:
        return _env_flag("FORWARD_TO_BEATS_MAP", default=True)

    @classmethod
    def peripheral_configuration(cls) -> str:
        return os.environ.get("PERIPHERAL_CONFIGURATION", "default")
