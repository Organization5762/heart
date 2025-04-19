import os
import platform
from typing import Iterator

import pygame
import serial.tools.list_ports


os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
REQUEST_JOYSTICK_MODULE_RESET = pygame.event.custom_type()


class Configuration:
    @classmethod
    def is_pi(cls):
        return platform.system() == "Linux" or bool(os.environ.get("ON_PI", False))

    @classmethod
    def is_profiling_mode(cls) -> bool:
        return bool(os.environ.get("PROFILING_MODE", False))


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
    if platform.system() == 'Darwin':  # macOS
        # On macOS, use pyserial but filter results that match the prefix
        for port in serial.tools.list_ports.comports():
            port_name = os.path.basename(port.device)
            if prefix.lower() in port.description.lower() or prefix.lower() in port_name.lower():
                yield port.device
