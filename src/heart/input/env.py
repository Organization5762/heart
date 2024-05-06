import os
import platform


class Environment:
    @classmethod
    def is_pi(cls):
        return platform.system() == "Linux"
    
    @classmethod
    def is_profiling_mode(cls) -> bool:
        return bool(os.environ.get("PROFILING_MODE", False))