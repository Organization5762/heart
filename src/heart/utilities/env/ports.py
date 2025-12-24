import platform
from pathlib import Path
from typing import Iterator

import serial.tools.list_ports


def get_device_ports(prefix: str) -> Iterator[str]:
    base_port = Path("/dev/serial/by-id")

    directory_matches = tuple(_iter_directory_ports(base_port, prefix))
    if directory_matches:
        yield from directory_matches
        return

    # Fallback for macOS and other platforms
    if platform.system() == "Darwin":  # macOS
        yield from _iter_serial_ports(prefix)


def _iter_directory_ports(base_port: Path, prefix: str) -> Iterator[str]:
    """Yield ports in ``base_port`` whose names begin with ``prefix``."""

    try:
        if not base_port.exists():
            return
        for entry in base_port.iterdir():
            if entry.name.startswith(prefix):
                yield str(entry)
    except (FileNotFoundError, PermissionError):
        return


def _iter_serial_ports(prefix: str) -> Iterator[str]:
    """Yield serial devices whose metadata contains ``prefix``."""

    lower_prefix = prefix.lower()
    for port in serial.tools.list_ports.comports():
        port_name = Path(port.device).name
        description = getattr(port, "description", "")
        if lower_prefix in description.lower() or lower_prefix in port_name.lower():
            yield port.device
