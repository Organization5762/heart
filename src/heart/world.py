from __future__ import annotations

import math
from dataclasses import dataclass
from threading import Lock
from typing import final

# This bounds process memory while remaining well above the physical Heart fleet
# and the number of devices used by collocated simulator sessions.
DEFAULT_MAX_WORLD_DEVICES = 256


@final
@dataclass(frozen=True, slots=True)
class WorldPosition:
    """A position in meters within Heart's local world coordinate system."""

    x_m: float
    y_m: float
    z_m: float


@final
@dataclass(frozen=True, slots=True)
class WorldDimensions:
    """The physical size of a Heart device in meters."""

    width_m: float
    height_m: float
    depth_m: float


@final
@dataclass(frozen=True, slots=True)
class WorldDevice:
    """Identity and placement for one device known to this process."""

    id: str
    position: WorldPosition
    dimensions: WorldDimensions
    capabilities: tuple[str, ...] = ()


@final
@dataclass(frozen=True, slots=True)
class ActiveMode:
    """The local device and configuration selected for a mode."""

    mode_id: str
    configuration_id: str
    owner_device_id: str


@final
@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    """One atomic read of local world state."""

    revision: int
    devices: tuple[WorldDevice, ...]
    active_mode: ActiveMode | None


@final
class World:
    """Bounded, process-local device placement and active-mode service."""

    def __init__(self, *, max_devices: int = DEFAULT_MAX_WORLD_DEVICES) -> None:
        if isinstance(max_devices, bool) or not isinstance(max_devices, int):
            raise TypeError("max_devices must be an integer")
        if max_devices <= 0:
            raise ValueError("max_devices must be greater than zero")
        self._max_devices = max_devices
        self._devices: dict[str, WorldDevice] = {}
        self._active_mode: ActiveMode | None = None
        self._revision = 0
        self._lock = Lock()

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def snapshot(self) -> WorldSnapshot:
        with self._lock:
            devices = tuple(
                self._devices[device_id] for device_id in sorted(self._devices)
            )
            return WorldSnapshot(
                revision=self._revision,
                devices=devices,
                active_mode=self._active_mode,
            )

    def device(self, device_id: str) -> WorldDevice | None:
        _validate_id(device_id, "World device id")
        with self._lock:
            return self._devices.get(device_id)

    def put_device(self, device: WorldDevice) -> bool:
        """Add or replace a device, returning whether local state changed."""
        _validate_device(device)
        with self._lock:
            existing = self._devices.get(device.id)
            if existing == device:
                return False
            if existing is None and len(self._devices) >= self._max_devices:
                raise ValueError(
                    f"World device limit {self._max_devices} has been reached"
                )
            self._devices[device.id] = device
            self._revision += 1
            return True

    def select_mode(self, active_mode: ActiveMode) -> bool:
        """Select a mode owned by a registered device."""
        _validate_active_mode(active_mode)
        with self._lock:
            if active_mode.owner_device_id not in self._devices:
                raise ValueError(
                    f"Mode owner device {active_mode.owner_device_id!r} is "
                    "not registered in world state"
                )
            if self._active_mode == active_mode:
                return False
            self._active_mode = active_mode
            self._revision += 1
            return True


def _validate_device(device: WorldDevice) -> None:
    if not isinstance(device, WorldDevice):
        raise TypeError("device must be a WorldDevice")
    if not isinstance(device.position, WorldPosition):
        raise TypeError("device.position must be a WorldPosition")
    if not isinstance(device.dimensions, WorldDimensions):
        raise TypeError("device.dimensions must be WorldDimensions")
    if not isinstance(device.capabilities, tuple):
        raise TypeError("device.capabilities must be a tuple")
    _validate_id(device.id, "World device id")
    _require_finite(
        device.position.x_m,
        device.position.y_m,
        device.position.z_m,
        device.dimensions.width_m,
        device.dimensions.height_m,
        device.dimensions.depth_m,
    )
    if (
        min(
            device.dimensions.width_m,
            device.dimensions.height_m,
            device.dimensions.depth_m,
        )
        <= 0
    ):
        raise ValueError("World dimensions must be greater than zero")
    if any(
        not isinstance(capability, str)
        or not capability.strip()
        or capability != capability.strip()
        for capability in device.capabilities
    ):
        raise ValueError(
            "World device capabilities must be non-empty, trimmed strings"
        )
    if len(set(device.capabilities)) != len(device.capabilities):
        raise ValueError("World device capabilities must be unique")


def _validate_active_mode(active_mode: ActiveMode) -> None:
    if not isinstance(active_mode, ActiveMode):
        raise TypeError("active_mode must be an ActiveMode")
    _validate_id(active_mode.mode_id, "Mode id")
    _validate_id(active_mode.configuration_id, "Mode configuration id")
    _validate_id(active_mode.owner_device_id, "Mode owner device id")


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{name} must not contain leading or trailing whitespace")


def _require_finite(*values: float) -> None:
    if not all(
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in values
    ):
        raise ValueError("World coordinates and dimensions must be finite")
