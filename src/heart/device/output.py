from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

import reactivex
from reactivex.disposable import Disposable

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.radio import FlowToyPattern
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import pipe_in_background

logger = get_logger(__name__)


class OutputMessageKind(StrEnum):
    """Supported output message variants for stream-driven devices."""

    FRAME = "frame"
    PERIPHERAL = "peripheral"
    FLOWTOY_PATTERN = "flowtoy_pattern"
    FLOWTOY_SYNC = "flowtoy_sync"
    FLOWTOY_STOP_SYNC = "flowtoy_stop_sync"
    FLOWTOY_RESET_SYNC = "flowtoy_reset_sync"
    FLOWTOY_WAKE = "flowtoy_wake"
    FLOWTOY_POWER_OFF = "flowtoy_power_off"
    FLOWTOY_RAW_COMMAND = "flowtoy_raw_command"
    FLOWTOY_SET_WIFI = "flowtoy_set_wifi"
    FLOWTOY_SET_GLOBAL_CONFIG = "flowtoy_set_global_config"


@dataclass(frozen=True, slots=True)
class FlowToySyncRequest:
    """Describe a FlowToy sync request destined for a bridge."""

    timeout_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class FlowToyGroupRequest:
    """Describe a FlowToy group-scoped control request."""

    group_id: int = 0
    group_is_public: bool = False


@dataclass(frozen=True, slots=True)
class FlowToyWifiRequest:
    """Describe a FlowToy bridge Wi-Fi credential update."""

    ssid: str
    password: str


@dataclass(frozen=True, slots=True)
class FlowToyGlobalConfigRequest:
    """Describe a FlowToy bridge global configuration update."""

    key: str
    value: int = 2


@dataclass(frozen=True, slots=True)
class OutputMessage:
    """Typed message sent to an output device from an asynchronous stream."""

    kind: OutputMessageKind
    payload: object

    @classmethod
    def frame(cls, payload: bytes | bytearray | memoryview) -> "OutputMessage":
        return cls(kind=OutputMessageKind.FRAME, payload=bytes(payload))

    @classmethod
    def peripheral(
        cls, payload: PeripheralMessageEnvelope[Any]
    ) -> "OutputMessage":
        return cls(kind=OutputMessageKind.PERIPHERAL, payload=payload)

    @classmethod
    def flowtoy_pattern(cls, payload: FlowToyPattern) -> "OutputMessage":
        return cls(kind=OutputMessageKind.FLOWTOY_PATTERN, payload=payload)

    @classmethod
    def flowtoy_sync(
        cls, timeout_seconds: float = 0.0
    ) -> "OutputMessage":
        return cls(
            kind=OutputMessageKind.FLOWTOY_SYNC,
            payload=FlowToySyncRequest(timeout_seconds=timeout_seconds),
        )

    @classmethod
    def flowtoy_stop_sync(cls) -> "OutputMessage":
        return cls(kind=OutputMessageKind.FLOWTOY_STOP_SYNC, payload=None)

    @classmethod
    def flowtoy_reset_sync(cls) -> "OutputMessage":
        return cls(kind=OutputMessageKind.FLOWTOY_RESET_SYNC, payload=None)

    @classmethod
    def flowtoy_wake(
        cls, *, group_id: int = 0, group_is_public: bool = False
    ) -> "OutputMessage":
        return cls(
            kind=OutputMessageKind.FLOWTOY_WAKE,
            payload=FlowToyGroupRequest(
                group_id=group_id,
                group_is_public=group_is_public,
            ),
        )

    @classmethod
    def flowtoy_power_off(
        cls, *, group_id: int = 0, group_is_public: bool = False
    ) -> "OutputMessage":
        return cls(
            kind=OutputMessageKind.FLOWTOY_POWER_OFF,
            payload=FlowToyGroupRequest(
                group_id=group_id,
                group_is_public=group_is_public,
            ),
        )

    @classmethod
    def flowtoy_raw_command(cls, command: str) -> "OutputMessage":
        return cls(kind=OutputMessageKind.FLOWTOY_RAW_COMMAND, payload=command)

    @classmethod
    def flowtoy_set_wifi(cls, *, ssid: str, password: str) -> "OutputMessage":
        return cls(
            kind=OutputMessageKind.FLOWTOY_SET_WIFI,
            payload=FlowToyWifiRequest(ssid=ssid, password=password),
        )

    @classmethod
    def flowtoy_set_global_config(
        cls,
        *,
        key: str,
        value: int = 2,
    ) -> "OutputMessage":
        return cls(
            kind=OutputMessageKind.FLOWTOY_SET_GLOBAL_CONFIG,
            payload=FlowToyGlobalConfigRequest(key=key, value=value),
        )


class OutputDevice:
    """Consume typed output messages, optionally from a shared observable stream."""

    def emit(self, message: OutputMessage) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def bind(self, stream: reactivex.Observable[OutputMessage]) -> Disposable:
        """Drain a shared observable into this device on a background thread."""

        return pipe_in_background(stream).subscribe(
            on_next=self.emit,
            on_error=self._log_stream_error,
        )

    def _log_stream_error(self, error: Exception) -> None:
        logger.error("Output device stream failed", exc_info=error)


class LegacyOutputSender(Protocol):
    """Backward-compatible output sender signature used by existing transports."""

    def send(self, kind: str, payload: object) -> None:
        """Send an untyped output payload."""


def dispatch_output(
    target: OutputDevice | LegacyOutputSender,
    message: OutputMessage,
) -> None:
    """Send an output message through the new API with legacy fallback."""

    emit = getattr(target, "emit", None)
    if callable(emit):
        emit(message)
        return
    target.send(message.kind.value, message.payload)
