"""Adapters for streaming proprietary 2.4 GHz packets"""

from __future__ import annotations

import importlib
import json
import os
import threading
from dataclasses import dataclass
from typing import Any, Iterator, Mapping

from heart.peripheral.core import Peripheral
from heart.peripheral.input_payloads.radio import RadioPacket
from heart.utilities.logging import get_logger

serial: Any
try:  # pragma: no cover - optional dependency on host systems
    serial = importlib.import_module("serial")
except ModuleNotFoundError:  # pragma: no cover - pyserial may be unavailable
    serial = None
except Exception:  # pragma: no cover - defensive catch for partial installs
    serial = None

logger = get_logger(__name__)

@dataclass(slots=True)
class RawRadioPacket:
    """Low-level representation produced by firmware drivers."""

    payload: bytes = b""
    frequency_hz: float | None = None
    channel: float | None = None
    modulation: str | None = None
    rssi_dbm: float | None = None
    metadata: Mapping[str, Any] | None = None


class RadioDriver:
    """Interface consumed by :class:`RadioPeripheral`."""

    def packets(self) -> Iterator[RawRadioPacket]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - optional hook
        """Release any underlying resources."""


class SerialRadioDriver(RadioDriver):
    """Reads newline-delimited JSON packets from a USB radio bridge."""

    ENV_PORT = "HEART_RADIO_PORT"
    DEFAULT_BAUDRATE = 115_200
    DEFAULT_TIMEOUT = 1.0

    def __init__(
        self,
        *,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        reconnect_delay: float = 1.0,
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

    @property
    def port(self) -> str:
        return self._port

    def packets(self) -> Iterator[RawRadioPacket]:
        """Yield packets until :meth:`close` is invoked."""

        while not self._stop_event.is_set():
            try:
                with self._open_serial() as handle:
                    yield from self._drain_serial(handle)
            except ModuleNotFoundError:
                raise
            except Exception:  # pragma: no cover - defensive reconnect loop
                logger.exception("Radio serial driver failed; retrying")
                if self._stop_event.wait(self._reconnect_delay):
                    break

    def close(self) -> None:
        self._stop_event.set()

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _open_serial(self) -> Any:  # pragma: no cover - thin wrapper around pyserial
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
            frequency_hz=self._extract_float(payload_mapping.get("frequency_hz")),
            channel=self._extract_float(payload_mapping.get("channel")),
            modulation=self._extract_str(payload_mapping.get("modulation")),
            rssi_dbm=self._extract_float(payload_mapping.get("rssi_dbm")),
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


class RadioPeripheral(Peripheral[RawRadioPacket]):
    """Bridge raw radio packets produced by firmware"""

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

    @classmethod
    def detect(cls) -> Iterator["RadioPeripheral"]:
        for driver in SerialRadioDriver.detect():
            yield cls(driver=driver)

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
        raise NotImplementedError("")
