import os
import platform
from typing import Iterator

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"


class Configuration:
    @classmethod
    def is_pi(cls):
        return platform.system() == "Linux" or bool(os.environ.get("ON_PI", False))

    @classmethod
    def is_profiling_mode(cls) -> bool:
        return bool(os.environ.get("PROFILING_MODE", False))


def get_device_ports(prefix: str) -> Iterator[str]:
    base_port = "/dev/serial/by-id"
    if os.path.exists(base_port):
        for port in os.listdir(base_port):
            if port.startswith(prefix):
                yield os.path.join(base_port, port)
