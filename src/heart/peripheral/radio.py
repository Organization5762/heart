"""Adapters for streaming and controlling proprietary 2.4 GHz packets."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from typing import Any, Iterator, Mapping

import reactivex
from reactivex.subject import Subject

from heart.peripheral.core import Input, Peripheral
from heart.peripheral.input_payloads.radio import RadioPacket
from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import

logger = get_logger(__name__)

serial = optional_import("serial", logger=logger)

DEFAULT_RADIO_BAUDRATE = 115_200
DEFAULT_RADIO_TIMEOUT_SECONDS = 1.0
DEFAULT_RADIO_RECONNECT_DELAY_SECONDS = 1.0
FLOWTOY_RAW_COMMAND_EVENT = "peripheral.radio.command.raw"
FLOWTOY_SYNC_EVENT = "peripheral.radio.flowtoy.sync"
FLOWTOY_STOP_SYNC_EVENT = "peripheral.radio.flowtoy.stop_sync"
FLOWTOY_RESET_SYNC_EVENT = "peripheral.radio.flowtoy.reset_sync"
FLOWTOY_PATTERN_EVENT = "peripheral.radio.flowtoy.pattern"
FLOWTOY_WAKE_EVENT = "peripheral.radio.flowtoy.wake"
FLOWTOY_POWER_OFF_EVENT = "peripheral.radio.flowtoy.power_off"
FLOWTOY_SET_WIFI_EVENT = "peripheral.radio.flowtoy.set_wifi"
FLOWTOY_SET_GLOBAL_CONFIG_EVENT = "peripheral.radio.flowtoy.set_global_config"


@dataclass(frozen=True, slots=True)
class FlowToyPattern:
    """Flowtoys bridge pattern command payload."""

    group_id: int = 0
    group_is_public: bool = False
    page: int = 0
    mode: int = 0
    actives: int = 0
    hue_offset: int = 0
    saturation: int = 0
    brightness: int = 0
    speed: int = 0
    density: int = 0
    lfo1: int = 0
    lfo2: int = 0
    lfo3: int = 0
    lfo4: int = 0

    def to_serial_command(self) -> str:
        prefix = "P" if self.group_is_public else "p"
        fields = (
            self.group_id,
            self.page,
            self.mode,
            self.actives,
            self.hue_offset,
            self.saturation,
            self.brightness,
            self.speed,
            self.density,
            self.lfo1,
            self.lfo2,
            self.lfo3,
            self.lfo4,
        )
        encoded_fields = ",".join(str(int(value)) for value in fields)
        return f"{prefix}{encoded_fields}"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "FlowToyPattern":
        return cls(
            group_id=_mapping_int(data, "group_id", "groupID"),
            group_is_public=_mapping_bool(data, "group_is_public", "groupIsPublic"),
            page=_mapping_int(data, "page"),
            mode=_mapping_int(data, "mode"),
            actives=_mapping_int(data, "actives"),
            hue_offset=_mapping_int(data, "hue_offset", "hueOffset"),
            saturation=_mapping_int(data, "saturation"),
            brightness=_mapping_int(data, "brightness"),
            speed=_mapping_int(data, "speed"),
            density=_mapping_int(data, "density"),
            lfo1=_mapping_int(data, "lfo1"),
            lfo2=_mapping_int(data, "lfo2"),
            lfo3=_mapping_int(data, "lfo3"),
            lfo4=_mapping_int(data, "lfo4"),
        )


def _mapping_value(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _mapping_int(data: Mapping[str, Any], *keys: str) -> int:
    value = _mapping_value(data, *keys)
    if value is None:
        return 0
    return int(value)


def _mapping_bool(data: Mapping[str, Any], *keys: str) -> bool:
    value = _mapping_value(data, *keys)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass(slots=True)
class RawRadioPacket:
    """Low-level representation produced by firmware drivers."""

    payload: bytes = b""
    protocol: str | None = None
    frequency_hz: float | None = None
    channel: float | None = None
    bitrate_kbps: float | None = None
    modulation: str | None = None
    crc_ok: bool | None = None
    rssi_dbm: float | None = None
    decoded: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] | None = None


class RadioDriver:
    """Interface consumed by :class:`RadioPeripheral`."""

    def packets(self) -> Iterator[RawRadioPacket]:  # pragma: no cover - interface
        raise NotImplementedError

    def send_raw_command(self, command: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - optional hook
        """Release any underlying resources."""


class SerialRadioDriver(RadioDriver):
    """Read newline-delimited packets and write bridge commands over serial."""

    ENV_PORT = "HEART_RADIO_PORT"

    def __init__(
        self,
        *,
        port: str,
        baudrate: int = DEFAULT_RADIO_BAUDRATE,
        timeout: float = DEFAULT_RADIO_TIMEOUT_SECONDS,
        reconnect_delay: float = DEFAULT_RADIO_RECONNECT_DELAY_SECONDS,
        serial_module: Any | None = None,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._reconnect_delay = max(0.0, reconnect_delay)
        self._serial_module = serial_module or serial
        if self._serial_module is None:
            raise ModuleNotFoundError(
                "pyserial is required for SerialRadioDriver but is not installed"
            )

        self._stop_event = threading.Event()
        self._handle_lock = threading.Lock()
        self._active_handle: Any | None = None

    @property
    def port(self) -> str:
        return self._port

    def packets(self) -> Iterator[RawRadioPacket]:
        """Yield packets until :meth:`close` is invoked."""

        while not self._stop_event.is_set():
            try:
                with self._open_serial() as handle:
                    with self._handle_lock:
                        self._active_handle = handle
                    try:
                        yield from self._drain_serial(handle)
                    finally:
                        with self._handle_lock:
                            if self._active_handle is handle:
                                self._active_handle = None
            except ModuleNotFoundError:
                raise
            except Exception:  # pragma: no cover - defensive reconnect loop
                logger.exception("Radio serial driver failed; retrying")
                if self._stop_event.wait(self._reconnect_delay):
                    break

    def send_raw_command(self, command: str) -> None:
        encoded_command = self._encode_command(command)
        with self._handle_lock:
            active_handle = self._active_handle
            if active_handle is not None:
                self._write_to_handle(active_handle, encoded_command)
                return

        with self._open_serial() as handle:
            self._write_to_handle(handle, encoded_command)

    def close(self) -> None:
        self._stop_event.set()
        with self._handle_lock:
            handle = self._active_handle
        if handle is None:
            return
        try:
            handle.close()
        except Exception:
            logger.debug("Ignoring serial close failure for %s", self._port, exc_info=True)

    @classmethod
    def detect(cls) -> Iterator["SerialRadioDriver"]:
        """Create drivers for ports enumerated in ``HEART_RADIO_PORT``."""

        if serial is None:
            logger.debug("pyserial not available; skipping radio driver detection")
            return

        env_value = os.environ.get(cls.ENV_PORT, "")
        if not env_value:
            return

        for candidate in env_value.split(","):
            port = candidate.strip()
            if not port:
                continue
            try:
                yield cls(port=port)
            except ModuleNotFoundError:
                logger.debug(
                    "pyserial missing while initialising SerialRadioDriver for %s", port
                )

    def _open_serial(self) -> Any:  # pragma: no cover - thin wrapper around pyserial
        if self._serial_module is None:
            raise ModuleNotFoundError(
                "pyserial is required for SerialRadioDriver but is not installed"
            )
        return self._serial_module.Serial(
            self._port,
            self._baudrate,
            timeout=self._timeout,
        )

    def _drain_serial(self, handle: Any) -> Iterator[RawRadioPacket]:
        while not self._stop_event.is_set():
            raw = handle.readline()
            if not raw:
                continue
            packet = self._decode(raw)
            if packet is not None:
                yield packet

    def _decode(self, raw: bytes) -> RawRadioPacket | None:
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            return None

        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            logger.debug("Ignoring malformed radio payload: %s", text)
            return None

        if not isinstance(message, Mapping):
            logger.debug("Ignoring non-mapping radio payload: %s", message)
            return None

        payload = message.get("data")
        payload_mapping: Mapping[str, Any]
        if isinstance(payload, Mapping):
            payload_mapping = payload
        else:
            payload_mapping = {}

        return RawRadioPacket(
            payload=self._extract_payload(payload_mapping.get("payload")),
            protocol=self._extract_str(payload_mapping.get("protocol")),
            frequency_hz=self._extract_float(payload_mapping.get("frequency_hz")),
            channel=self._extract_float(payload_mapping.get("channel")),
            bitrate_kbps=self._extract_float(payload_mapping.get("bitrate_kbps")),
            modulation=self._extract_str(payload_mapping.get("modulation")),
            crc_ok=self._extract_bool(payload_mapping.get("crc_ok")),
            rssi_dbm=self._extract_float(payload_mapping.get("rssi_dbm")),
            decoded=self._extract_metadata(payload_mapping.get("decoded")),
            metadata=self._extract_metadata(payload_mapping.get("metadata")),
        )

    def _extract_float(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                logger.debug("Failed to parse float component from %s", value)
        return None

    def _extract_str(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    def _extract_bool(self, value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            return None
        return bool(value)

    def _extract_payload(self, value: Any) -> bytes:
        if value is None:
            return b""
        if isinstance(value, (bytes, bytearray, memoryview)):
            return bytes(value)
        if isinstance(value, str):
            return value.encode("utf-8")
        if isinstance(value, (list, tuple)):
            try:
                return bytes(int(item) & 0xFF for item in value)
            except (TypeError, ValueError):
                logger.debug("Ignoring malformed radio payload sequence: %s", value)
                return b""
        logger.debug("Unsupported radio payload type: %s", type(value).__name__)
        return b""

    def _extract_metadata(self, value: Any) -> Mapping[str, Any] | None:
        if isinstance(value, Mapping):
            return dict(value)
        return None

    def _encode_command(self, command: str) -> bytes:
        stripped = command.rstrip("\n")
        return f"{stripped}\n".encode("utf-8")

    def _write_to_handle(self, handle: Any, command: bytes) -> None:
        handle.write(command)
        if hasattr(handle, "flush"):
            handle.flush()


class RadioPeripheral(Peripheral[RadioPacket]):
    """Bridge raw radio packets and Flowtoys bridge commands."""

    EVENT_TYPE = RadioPacket.EVENT_TYPE

    def __init__(
        self,
        *,
        driver: RadioDriver,
    ) -> None:
        super().__init__()
        self._driver = driver
        self._stop_event = threading.Event()
        self._latest_packet: RawRadioPacket | None = None
        self._packet_subject: Subject[RadioPacket] = Subject()

    @classmethod
    def detect(cls) -> Iterator["RadioPeripheral"]:
        for driver in SerialRadioDriver.detect():
            yield cls(driver=driver)

    def _event_stream(self) -> reactivex.Observable[RadioPacket]:
        return self._packet_subject

    @property
    def latest_packet(self) -> RawRadioPacket | None:
        return self._latest_packet

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self._driver.close()
        except Exception:
            logger.debug("Ignoring error while closing radio driver", exc_info=True)

    def run(self) -> None:
        for packet in self._driver.packets():
            if self._stop_event.is_set():
                break
            self.process_packet(packet)
        self._stop_event.clear()

    def process_packet(self, packet: RawRadioPacket) -> None:
        radio_packet = RadioPacket(
            protocol=packet.protocol,
            frequency_hz=packet.frequency_hz,
            channel=packet.channel,
            bitrate_kbps=packet.bitrate_kbps,
            modulation=packet.modulation,
            crc_ok=packet.crc_ok,
            rssi_dbm=packet.rssi_dbm,
            payload=packet.payload,
            decoded=packet.decoded,
            metadata=packet.metadata,
        )
        self._latest_packet = packet
        self._packet_subject.on_next(radio_packet)

    def handle_input(self, input: Input) -> None:
        data = input.data
        if not isinstance(data, Mapping):
            logger.debug("Ignoring radio input with malformed payload: %s", input.data)
            return

        if input.event_type == FLOWTOY_RAW_COMMAND_EVENT:
            command = data.get("command")
            if not isinstance(command, str) or not command.strip():
                logger.debug("Ignoring empty raw radio command payload: %s", data)
                return
            self.send_raw_command(command)
            return

        if input.event_type == FLOWTOY_SYNC_EVENT:
            self.sync_flow_toys(timeout_seconds=float(data.get("timeout_seconds", 0.0)))
            return

        if input.event_type == FLOWTOY_STOP_SYNC_EVENT:
            self.stop_flow_toy_sync()
            return

        if input.event_type == FLOWTOY_RESET_SYNC_EVENT:
            self.reset_flow_toy_sync()
            return

        if input.event_type == FLOWTOY_PATTERN_EVENT:
            self.set_flow_toy_pattern(FlowToyPattern.from_mapping(data))
            return

        if input.event_type == FLOWTOY_WAKE_EVENT:
            self.wake_flow_toys(
                group_id=_mapping_int(data, "group_id", "groupID"),
                group_is_public=_mapping_bool(data, "group_is_public", "groupIsPublic"),
            )
            return

        if input.event_type == FLOWTOY_POWER_OFF_EVENT:
            self.power_off_flow_toys(
                group_id=_mapping_int(data, "group_id", "groupID"),
                group_is_public=_mapping_bool(data, "group_is_public", "groupIsPublic"),
            )
            return

        if input.event_type == FLOWTOY_SET_WIFI_EVENT:
            ssid = _mapping_value(data, "ssid")
            password = _mapping_value(data, "password")
            if not isinstance(ssid, str) or not isinstance(password, str):
                logger.debug("Ignoring malformed Flowtoys Wi-Fi payload: %s", data)
                return
            self.set_flow_toy_wifi(ssid=ssid, password=password)
            return

        if input.event_type == FLOWTOY_SET_GLOBAL_CONFIG_EVENT:
            key = _mapping_value(data, "key", "name")
            value = _mapping_int(data, "value")
            if not isinstance(key, str) or not key:
                logger.debug("Ignoring malformed Flowtoys global config payload: %s", data)
                return
            self.set_flow_toy_global_config(key=key, value=value)

    def send_raw_command(self, command: str) -> None:
        self._driver.send_raw_command(command)

    def sync_flow_toys(self, *, timeout_seconds: float = 0.0) -> None:
        self.send_raw_command(f"s{timeout_seconds:g}")

    def stop_flow_toy_sync(self) -> None:
        self.send_raw_command("S")

    def reset_flow_toy_sync(self) -> None:
        self.send_raw_command("a")

    def wake_flow_toys(self, *, group_id: int = 0, group_is_public: bool = False) -> None:
        prefix = "W" if group_is_public else "w"
        self.send_raw_command(f"{prefix}{int(group_id)}")

    def power_off_flow_toys(
        self,
        *,
        group_id: int = 0,
        group_is_public: bool = False,
    ) -> None:
        prefix = "Z" if group_is_public else "z"
        self.send_raw_command(f"{prefix}{int(group_id)}")

    def set_flow_toy_pattern(self, pattern: FlowToyPattern) -> None:
        self.send_raw_command(pattern.to_serial_command())

    def set_flow_toy_wifi(self, *, ssid: str, password: str) -> None:
        self.send_raw_command(f"n{ssid},{password}")

    def set_flow_toy_global_config(self, *, key: str, value: int = 2) -> None:
        self.send_raw_command(f"g{key},{int(value)}")
