import os
import platform

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

class Configuration:
    @classmethod
    def is_pi(cls):
        return platform.system() == "Linux" or bool(os.environ.get("ON_PI", False))

    @classmethod
    def is_profiling_mode(cls) -> bool:
        return bool(os.environ.get("PROFILING_MODE", False))
