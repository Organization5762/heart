from __future__ import annotations

from dataclasses import dataclass

from heart.device.output import (FlowToyGlobalConfigRequest,
                                 FlowToyGroupRequest, FlowToySyncRequest,
                                 FlowToyWifiRequest, OutputDevice,
                                 OutputMessage, OutputMessageKind)
from heart.peripheral.radio import FlowToyPattern, RadioDriver


@dataclass
class FlowToyBridgeClient:
    """Typed serial-bus client for the FlowToy bridge command surface."""

    driver: RadioDriver

    def send_raw_command(self, command: str) -> None:
        if not isinstance(command, str) or not command.strip():
            raise TypeError("FlowToy raw commands require a non-empty string")
        self.driver.send_raw_command(command)

    def sync(self, *, timeout_seconds: float = 0.0) -> None:
        self.send_raw_command(f"s{timeout_seconds:g}")

    def stop_sync(self) -> None:
        self.send_raw_command("S")

    def reset_sync(self) -> None:
        self.send_raw_command("a")

    def wake(self, *, group_id: int = 0, group_is_public: bool = False) -> None:
        prefix = "W" if group_is_public else "w"
        self.send_raw_command(f"{prefix}{int(group_id)}")

    def power_off(
        self,
        *,
        group_id: int = 0,
        group_is_public: bool = False,
    ) -> None:
        prefix = "Z" if group_is_public else "z"
        self.send_raw_command(f"{prefix}{int(group_id)}")

    def set_pattern(self, pattern: FlowToyPattern) -> None:
        self.send_raw_command(pattern.to_serial_command())

    def set_wifi(self, *, ssid: str, password: str) -> None:
        self.send_raw_command(f"n{ssid},{password}")

    def set_global_config(self, *, key: str, value: int = 2) -> None:
        self.send_raw_command(f"g{key},{int(value)}")


@dataclass
class FlowToyBridgeOutputDevice(OutputDevice):
    """Serialize FlowToy output messages into bridge commands."""

    driver: RadioDriver

    def __post_init__(self) -> None:
        self.client = FlowToyBridgeClient(driver=self.driver)

    def emit(self, message: OutputMessage) -> None:
        self._dispatch_message(message)

    def _dispatch_message(self, message: OutputMessage) -> None:
        if message.kind == OutputMessageKind.FLOWTOY_PATTERN:
            payload = message.payload
            if not isinstance(payload, FlowToyPattern):
                raise TypeError("FlowToy pattern messages require a FlowToyPattern payload")
            self.client.set_pattern(payload)
            return

        if message.kind == OutputMessageKind.FLOWTOY_SYNC:
            payload = message.payload
            if not isinstance(payload, FlowToySyncRequest):
                raise TypeError("FlowToy sync messages require a FlowToySyncRequest payload")
            self.client.sync(timeout_seconds=payload.timeout_seconds)
            return

        if message.kind == OutputMessageKind.FLOWTOY_STOP_SYNC:
            self.client.stop_sync()
            return

        if message.kind == OutputMessageKind.FLOWTOY_RESET_SYNC:
            self.client.reset_sync()
            return

        if message.kind == OutputMessageKind.FLOWTOY_WAKE:
            payload = message.payload
            if not isinstance(payload, FlowToyGroupRequest):
                raise TypeError("FlowToy wake messages require a FlowToyGroupRequest payload")
            self.client.wake(
                group_id=payload.group_id,
                group_is_public=payload.group_is_public,
            )
            return

        if message.kind == OutputMessageKind.FLOWTOY_POWER_OFF:
            payload = message.payload
            if not isinstance(payload, FlowToyGroupRequest):
                raise TypeError(
                    "FlowToy power-off messages require a FlowToyGroupRequest payload"
                )
            self.client.power_off(
                group_id=payload.group_id,
                group_is_public=payload.group_is_public,
            )
            return

        if message.kind == OutputMessageKind.FLOWTOY_RAW_COMMAND:
            payload = message.payload
            if not isinstance(payload, str):
                raise TypeError("FlowToy raw-command messages require a non-empty string")
            self.client.send_raw_command(payload)
            return

        if message.kind == OutputMessageKind.FLOWTOY_SET_WIFI:
            payload = message.payload
            if not isinstance(payload, FlowToyWifiRequest):
                raise TypeError("FlowToy Wi-Fi messages require a FlowToyWifiRequest payload")
            self.client.set_wifi(ssid=payload.ssid, password=payload.password)
            return

        if message.kind == OutputMessageKind.FLOWTOY_SET_GLOBAL_CONFIG:
            payload = message.payload
            if not isinstance(payload, FlowToyGlobalConfigRequest):
                raise TypeError(
                    "FlowToy global-config messages require a FlowToyGlobalConfigRequest payload"
                )
            self.client.set_global_config(key=payload.key, value=payload.value)
            return

        raise ValueError(f"Unsupported FlowToy output message kind: {message.kind}")
