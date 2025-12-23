import os
import platform
import re
from dataclasses import dataclass
from functools import cache
from typing import Iterator

import serial.tools.list_ports

from heart.device.isolated_render import DEFAULT_SOCKET_PATH

TRUE_FLAG_VALUES = {"true", "1", "yes", "on"}


def _env_flag(env_var: str, *, default: bool = False) -> bool:
    """Return the boolean value of ``env_var`` respecting common true strings."""

    value = os.environ.get(env_var)
    if value is None:
        return default
    return value.strip().lower() in TRUE_FLAG_VALUES


def _env_int(
    env_var: str, *, default: int, minimum: int | None = None
) -> int:
    """Return the integer value of ``env_var`` with optional bounds checking."""

    value = os.environ.get(env_var)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{env_var} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{env_var} must be at least {minimum}")
    return parsed


@dataclass
class Pi:
    version: int


class Configuration:
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
            m = re.search(r"Raspberry Pi (\d+)", model)
            if not m:
                raise ValueError(f"Couldn't parse Pi model from {model!r}")
            return Pi(version=int(m.group(1)))

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

    @classmethod
    def reactivex_background_max_workers(cls) -> int:
        return _env_int("HEART_RX_BACKGROUND_MAX_WORKERS", default=4, minimum=1)

    @classmethod
    def reactivex_input_max_workers(cls) -> int:
        return _env_int("HEART_RX_INPUT_MAX_WORKERS", default=2, minimum=1)

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

    @classmethod
    def signal_fft_correlation_threshold(cls) -> int:
        return _env_int("HEART_SIGNAL_FFT_THRESHOLD", default=50_000, minimum=1)

    @classmethod
    def signal_fft_pad_mode(cls) -> str:
        mode = os.environ.get("HEART_SIGNAL_FFT_PAD_MODE", "next_pow2").strip().lower()
        if mode not in {"exact", "next_pow2"}:
            raise ValueError(
                "HEART_SIGNAL_FFT_PAD_MODE must be 'exact' or 'next_pow2'"
            )
        return mode


def get_device_ports(prefix: str) -> Iterator[str]:
    base_port = "/dev/serial/by-id"

    directory_matches = tuple(_iter_directory_ports(base_port, prefix))
    if directory_matches:
        yield from directory_matches
        return

    # Fallback for macOS and other platforms
    if platform.system() == "Darwin":  # macOS
        yield from _iter_serial_ports(prefix)


def _iter_directory_ports(base_port: str, prefix: str) -> Iterator[str]:
    """Yield ports in ``base_port`` whose names begin with ``prefix``."""

    try:
        if not os.path.exists(base_port):
            return
        for entry in os.listdir(base_port):
            if entry.startswith(prefix):
                yield os.path.join(base_port, entry)
    except (FileNotFoundError, PermissionError):
        return


def _iter_serial_ports(prefix: str) -> Iterator[str]:
    """Yield serial devices whose metadata contains ``prefix``."""

    lower_prefix = prefix.lower()
    for port in serial.tools.list_ports.comports():
        port_name = os.path.basename(port.device)
        description = getattr(port, "description", "")
        if lower_prefix in description.lower() or lower_prefix in port_name.lower():
            yield port.device
