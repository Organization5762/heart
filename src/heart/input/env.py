import os
import platform


class Environment:
    @classmethod
    def is_pi(cls):
        return platform.system() == "Linux" or bool(os.environ.get("ON_PI", False))

    @classmethod
    def is_profiling_mode(cls) -> bool:
        return bool(os.environ.get("PROFILING_MODE", False))
