from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ControllerPairingTarget:
    label: str
    address: str
    color: str


@dataclass(frozen=True)
class ControllerPairingDeviceState:
    target: ControllerPairingTarget
    name: str | None = None
    seen: bool = False
    paired: bool = False
    trusted: bool = False
    connected: bool = False
    pairing: bool = False
    last_action: str = "waiting"
    error: str | None = None


@dataclass(frozen=True)
class ControllerPairingState:
    devices: tuple[ControllerPairingDeviceState, ...] = field(default_factory=tuple)
    scanning: bool = False
    cycle: int = 0
    last_message: str = "idle"
