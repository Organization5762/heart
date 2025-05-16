import os
import platform
import re
from dataclasses import dataclass
from typing import Iterator
from functools import cache

import serial.tools.list_ports
from pygame.event import custom_type


@dataclass
class Pi:
    version: int


class Configuration:
    @classmethod
    @cache
    def is_pi(cls) -> bool:
        return platform.system() == "Linux" or bool(os.environ.get("ON_PI", False))

    @classmethod
    def pi(cls) -> Pi | None:
        if not cls.is_pi():
            return None

        with open("/proc/device-tree/model", "rb") as fp:
            raw = fp.read()
            model = raw.decode("ascii", errors="ignore").rstrip("\x00\n")

            # Match “Raspberry Pi X” and capture X
            m = re.search(r"Raspberry Pi (\d+)", model)
            if not m:
                raise ValueError(f"Couldn't parse Pi model from {model!r}")
            return Pi(version=int(m.group(1)))

    @classmethod
    def is_profiling_mode(cls) -> bool:
        return bool(os.environ.get("PROFILING_MODE", False))

    @classmethod
    def is_debug_mode(cls) -> bool:
        return bool(os.environ.get("DEBUG_MODE", False))


def get_device_ports(prefix: str) -> Iterator[str]:
    base_port = "/dev/serial/by-id"

    try:
        if os.path.exists(base_port):
            for port in os.listdir(base_port):
                if port.startswith(prefix):
                    yield os.path.join(base_port, port)
            return  # Exit if we successfully found ports
    except (FileNotFoundError, PermissionError):
        pass  # Continue to fallback methods

    # Fallback for macOS and other platforms
    if platform.system() == "Darwin":  # macOS
        # On macOS, use pyserial but filter results that match the prefix
        for port in serial.tools.list_ports.comports():
            port_name = os.path.basename(port.device)
            if (
                prefix.lower() in port.description.lower()
                or prefix.lower() in port_name.lower()
            ):
                yield port.device
