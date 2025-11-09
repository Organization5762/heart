import os
import platform
import re
from dataclasses import dataclass
from functools import cache
from typing import Iterator

import serial.tools.list_ports

from heart.device.isolated_render import DEFAULT_SOCKET_PATH

TRUE_FLAG_VALUES = {"true", "1"}


def _env_flag(env_var: str, *, default: bool = False) -> bool:
    value = os.environ.get(env_var)
    if value is None:
        return default
    return value.lower() in TRUE_FLAG_VALUES


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
    def enable_input_event_bus(cls) -> bool:
        return _env_flag("ENABLE_INPUT_EVENT_BUS")

    @classmethod
    def peripheral_configuration(cls) -> str:
        return os.environ.get("PERIPHERAL_CONFIGURATION", "default")

    @classmethod
    def isolated_renderer_socket(cls) -> str | None:
        socket_path = os.environ.get("ISOLATED_RENDER_SOCKET")
        if socket_path == "":
            return None
        if socket_path is not None:
            return socket_path
        if cls.isolated_renderer_tcp_address() is not None:
            return None
        return DEFAULT_SOCKET_PATH

    @classmethod
    def isolated_renderer_tcp_address(cls) -> tuple[str, int] | None:
        host = os.environ.get("ISOLATED_RENDER_HOST")
        port = os.environ.get("ISOLATED_RENDER_PORT")
        if host and port:
            try:
                return host, int(port)
            except ValueError:
                raise ValueError(
                    "ISOLATED_RENDER_PORT must be an integer when ISOLATED_RENDER_HOST is set"
                )
        if host or port:
            raise ValueError(
                "Both ISOLATED_RENDER_HOST and ISOLATED_RENDER_PORT must be set together"
            )
        return None


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
