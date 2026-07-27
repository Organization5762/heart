from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from threading import Lock
from typing import cast, final

from manyfold.architecture.transport_rpc import (RpcCancellation, RpcEndpoint,
                                                 RpcRequest)
from manyfold.cluster import CommittedCommand, ControlCommand

WORLD_RPC_SERVICE = "heart.world"
GET_DEVICE_RPC_METHOD = "get_device"
GET_ACTIVE_MODE_RPC_METHOD = "get_active_mode"
PUT_DEVICE_COMMAND_KIND = "heart.world.device.put"
SELECT_MODE_COMMAND_KIND = "heart.world.mode.select"
COORDINATED_COMMAND_KINDS = frozenset(
    {
        PUT_DEVICE_COMMAND_KIND,
        SELECT_MODE_COMMAND_KIND,
    }
)
EXCLUDED_DURABLE_DATA_KINDS = frozenset(
    {
        "debug",
        "frame_tick",
        "microphone_sample",
        "navigation_event",
        "rendered_frame",
        "sensor_sample",
    }
)
_WIRE_VERSION = 1


@final
@dataclass(frozen=True, slots=True)
class WorldPosition:
    """A position in meters within the shared world coordinate system."""

    x_m: float
    y_m: float
    z_m: float


@final
@dataclass(frozen=True, slots=True)
class WorldDimensions:
    """The physical size of a device in meters."""

    width_m: float
    height_m: float
    depth_m: float


@final
@dataclass(frozen=True, slots=True)
class WorldDevice:
    """Durable, low-rate identity and placement for one Heart device."""

    id: str
    position: WorldPosition
    dimensions: WorldDimensions
    capabilities: tuple[str, ...] = ()


@final
@dataclass(frozen=True, slots=True)
class ActiveMode:
    """The coordinated owner and immutable configuration selected for a
    mode."""

    mode_id: str
    configuration_id: str
    owner_device_id: str


@final
@dataclass(frozen=True, slots=True)
class WorldDeviceRead:
    """One RPC device read with the applied Raft sequence used to answer it."""

    revision: int
    device: WorldDevice | None


@final
@dataclass(frozen=True, slots=True)
class ActiveModeRead:
    """One RPC mode read with the applied Raft sequence used to answer it."""

    revision: int
    active_mode: ActiveMode | None


@final
class StaleWorldResponseError(RuntimeError):
    """Raised when a server answers from an older applied Raft revision."""


def put_device_command(command_id: str, device: WorldDevice) -> ControlCommand:
    """Build the sole Raft command that changes durable device state."""
    _validate_device(device)
    return ControlCommand(
        command_id=command_id,
        kind=PUT_DEVICE_COMMAND_KIND,
        payload=_device_to_json(device),
    )


def select_mode_command(
    command_id: str,
    active_mode: ActiveMode,
) -> ControlCommand:
    """Build the sole Raft command that changes active mode ownership."""
    _validate_active_mode(active_mode)
    return ControlCommand(
        command_id=command_id,
        kind=SELECT_MODE_COMMAND_KIND,
        payload=_active_mode_to_json(active_mode),
    )


@final
class WorldState:
    """Thread-safe projection of Heart's bounded Raft control log."""

    def __init__(self) -> None:
        self._devices: dict[str, WorldDevice] = {}
        self._active_mode: ActiveMode | None = None
        self._applied_commands: dict[str, tuple[str, bytes]] = {}
        self._revision = 0
        self._lock = Lock()

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def device(self, device_id: str) -> WorldDeviceRead:
        _validate_id(device_id, "World device id")
        with self._lock:
            return WorldDeviceRead(
                revision=self._revision,
                device=self._devices.get(device_id),
            )

    def active_mode(self) -> ActiveModeRead:
        with self._lock:
            return ActiveModeRead(
                revision=self._revision,
                active_mode=self._active_mode,
            )

    def apply(self, command: CommittedCommand) -> bool:
        """Apply one committed command exactly once by stable command ID."""
        if not isinstance(command, CommittedCommand):
            raise TypeError("command must be a ManyFold CommittedCommand")
        if command.kind not in COORDINATED_COMMAND_KINDS:
            raise ValueError(
                f"command kind {command.kind!r} is outside Heart's durable "
                f"coordination boundary"
            )
        fingerprint = (command.kind, _json_bytes(command.payload))
        with self._lock:
            existing = self._applied_commands.get(command.command_id)
            if existing is not None:
                if existing != fingerprint:
                    raise ValueError(
                        f"command_id {command.command_id!r} names conflicting "
                        "Heart coordination content"
                    )
                return False
            expected_sequence = self._revision + 1
            if command.sequence != expected_sequence:
                raise ValueError(
                    f"Heart coordination sequence expected {expected_sequence}, "
                    f"observed {command.sequence}"
                )
            if command.kind == PUT_DEVICE_COMMAND_KIND:
                device = _device_from_json(command.payload)
                self._devices[device.id] = device
            else:
                active_mode = _active_mode_from_json(command.payload)
                if active_mode.owner_device_id not in self._devices:
                    raise ValueError(
                        f"Mode owner device {active_mode.owner_device_id!r} is "
                        "not registered in world state"
                    )
                self._active_mode = active_mode
            self._applied_commands[command.command_id] = fingerprint
            self._revision = command.sequence
            return True

    def apply_log(self, commands: Iterable[CommittedCommand]) -> int:
        """Apply a local ManyFold committed-log page in sequence order."""
        applied = 0
        for command in commands:
            if self.apply(command):
                applied += 1
        return applied


@final
class WorldRpcServer:
    """Typed, read-only world service on a ManyFold coordinator RPC
    endpoint."""

    def __init__(self, endpoint: RpcEndpoint, state: WorldState) -> None:
        if not isinstance(endpoint, RpcEndpoint):
            raise TypeError("endpoint must be a ManyFold RpcEndpoint")
        if not isinstance(state, WorldState):
            raise TypeError("state must be a WorldState")
        self._endpoint = endpoint
        self._state = state
        endpoint.register(
            WORLD_RPC_SERVICE,
            GET_DEVICE_RPC_METHOD,
            self._get_device,
        )
        endpoint.register(
            WORLD_RPC_SERVICE,
            GET_ACTIVE_MODE_RPC_METHOD,
            self._get_active_mode,
        )

    def dispose(self) -> None:
        self._endpoint.unregister(WORLD_RPC_SERVICE, GET_DEVICE_RPC_METHOD)
        self._endpoint.unregister(WORLD_RPC_SERVICE, GET_ACTIVE_MODE_RPC_METHOD)

    def _get_device(
        self,
        request: RpcRequest,
        cancellation: RpcCancellation,
    ) -> bytes:
        cancellation.raise_if_cancelled()
        payload = _json_object(request.payload, "world device RPC request")
        _require_wire_version(payload)
        device_id = _json_string(payload, "device_id")
        result = self._state.device(device_id)
        cancellation.raise_if_cancelled()
        return _json_bytes(
            {
                "version": _WIRE_VERSION,
                "revision": result.revision,
                "device": (
                    _device_to_json(result.device)
                    if result.device is not None
                    else None
                ),
            }
        )

    def _get_active_mode(
        self,
        request: RpcRequest,
        cancellation: RpcCancellation,
    ) -> bytes:
        cancellation.raise_if_cancelled()
        payload = _json_object(request.payload, "active mode RPC request")
        _require_wire_version(payload)
        result = self._state.active_mode()
        cancellation.raise_if_cancelled()
        return _json_bytes(
            {
                "version": _WIRE_VERSION,
                "revision": result.revision,
                "active_mode": (
                    _active_mode_to_json(result.active_mode)
                    if result.active_mode is not None
                    else None
                ),
            }
        )


@final
class WorldRpcClient:
    """Typed world read client with revision-based stale response rejection."""

    def __init__(
        self,
        endpoint: RpcEndpoint,
        *,
        minimum_revision: int = 0,
    ) -> None:
        if not isinstance(endpoint, RpcEndpoint):
            raise TypeError("endpoint must be a ManyFold RpcEndpoint")
        _require_non_negative_int(minimum_revision, "minimum_revision")
        self._endpoint = endpoint
        self._observed_revision = minimum_revision
        self._lock = Lock()

    @property
    def observed_revision(self) -> int:
        with self._lock:
            return self._observed_revision

    def get_device(
        self,
        device_id: str,
        *,
        timeout_seconds: float,
    ) -> WorldDeviceRead:
        _validate_id(device_id, "World device id")
        response = self._endpoint.call(
            WORLD_RPC_SERVICE,
            GET_DEVICE_RPC_METHOD,
            _json_bytes(
                {
                    "version": _WIRE_VERSION,
                    "device_id": device_id,
                }
            ),
            timeout_seconds=timeout_seconds,
        )
        payload = _json_object(response, "world device RPC response")
        _require_wire_version(payload)
        revision = _json_non_negative_int(payload, "revision")
        self._accept_revision(revision)
        device_value = payload.get("device")
        device = (
            None
            if device_value is None
            else _device_from_json(
                _json_mapping(device_value, "world device RPC device")
            )
        )
        return WorldDeviceRead(revision=revision, device=device)

    def get_active_mode(self, *, timeout_seconds: float) -> ActiveModeRead:
        response = self._endpoint.call(
            WORLD_RPC_SERVICE,
            GET_ACTIVE_MODE_RPC_METHOD,
            _json_bytes({"version": _WIRE_VERSION}),
            timeout_seconds=timeout_seconds,
        )
        payload = _json_object(response, "active mode RPC response")
        _require_wire_version(payload)
        revision = _json_non_negative_int(payload, "revision")
        self._accept_revision(revision)
        active_mode_value = payload.get("active_mode")
        active_mode = (
            None
            if active_mode_value is None
            else _active_mode_from_json(
                _json_mapping(active_mode_value, "active mode RPC value")
            )
        )
        return ActiveModeRead(revision=revision, active_mode=active_mode)

    def _accept_revision(self, revision: int) -> None:
        with self._lock:
            if revision < self._observed_revision:
                raise StaleWorldResponseError(
                    f"world RPC response revision {revision} is older than "
                    f"observed revision {self._observed_revision}"
                )
            self._observed_revision = revision


def _device_to_json(device: WorldDevice) -> dict[str, object]:
    return {
        "id": device.id,
        "position": {
            "x_m": device.position.x_m,
            "y_m": device.position.y_m,
            "z_m": device.position.z_m,
        },
        "dimensions": {
            "width_m": device.dimensions.width_m,
            "height_m": device.dimensions.height_m,
            "depth_m": device.dimensions.depth_m,
        },
        "capabilities": list(device.capabilities),
    }


def _device_from_json(value: Mapping[str, object]) -> WorldDevice:
    position = _json_mapping(value.get("position"), "device position")
    dimensions = _json_mapping(value.get("dimensions"), "device dimensions")
    capabilities_value = value.get("capabilities", [])
    if not isinstance(capabilities_value, list) or not all(
        isinstance(capability, str) for capability in capabilities_value
    ):
        raise ValueError("device capabilities must be a list of strings")
    device = WorldDevice(
        id=_json_string(value, "id"),
        position=WorldPosition(
            x_m=_json_number(position, "x_m"),
            y_m=_json_number(position, "y_m"),
            z_m=_json_number(position, "z_m"),
        ),
        dimensions=WorldDimensions(
            width_m=_json_number(dimensions, "width_m"),
            height_m=_json_number(dimensions, "height_m"),
            depth_m=_json_number(dimensions, "depth_m"),
        ),
        capabilities=tuple(capabilities_value),
    )
    _validate_device(device)
    return device


def _active_mode_to_json(active_mode: ActiveMode) -> dict[str, object]:
    return {
        "mode_id": active_mode.mode_id,
        "configuration_id": active_mode.configuration_id,
        "owner_device_id": active_mode.owner_device_id,
    }


def _active_mode_from_json(value: Mapping[str, object]) -> ActiveMode:
    active_mode = ActiveMode(
        mode_id=_json_string(value, "mode_id"),
        configuration_id=_json_string(value, "configuration_id"),
        owner_device_id=_json_string(value, "owner_device_id"),
    )
    _validate_active_mode(active_mode)
    return active_mode


def _validate_device(device: WorldDevice) -> None:
    if not isinstance(device, WorldDevice):
        raise TypeError("device must be a WorldDevice")
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
        not isinstance(capability, str) or not capability.strip()
        for capability in device.capabilities
    ):
        raise ValueError("World device capabilities must be non-empty strings")
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


def _require_finite(*values: float) -> None:
    if not all(
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in values
    ):
        raise ValueError("World coordinates and dimensions must be finite")


def _json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Heart coordination value must be finite JSON: {error}"
        ) from error


def _json_object(payload: bytes, name: str) -> Mapping[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} must be UTF-8 JSON: {error}") from error
    return _json_mapping(value, name)


def _json_mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _json_string(value: Mapping[str, object], field: str) -> str:
    field_value = value.get(field)
    if not isinstance(field_value, str) or not field_value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return field_value


def _json_number(value: Mapping[str, object], field: str) -> float:
    field_value = value.get(field)
    if (
        isinstance(field_value, bool)
        or not isinstance(field_value, (int, float))
        or not math.isfinite(field_value)
    ):
        raise ValueError(f"{field} must be a finite number")
    return float(field_value)


def _json_non_negative_int(value: Mapping[str, object], field: str) -> int:
    field_value = value.get(field)
    _require_non_negative_int(field_value, field)
    return cast(int, field_value)


def _require_non_negative_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _require_wire_version(value: Mapping[str, object]) -> None:
    version = value.get("version")
    if version != _WIRE_VERSION:
        raise ValueError(
            f"Heart world RPC version must be {_WIRE_VERSION}, observed {version!r}"
        )
