"""Receive-only FlowToy bridge harness for Feather-class boards.

REPL reproduction:
    1. Connect to the board REPL and import this module.
    2. Instantiate ``RadioBridgeRuntime`` with a stub ``gather_packet`` callable.
    3. Call ``runtime.run_once()`` to verify serial framing and identity replies.

The default ``code.py`` entry point is intentionally a schema-focused harness.
It provides the USB serial contract used by Totem while the real receive path
is implemented by board-specific radio code or the companion Arduino sketch in
this driver directory.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable

from heart_firmware_io import device_id, flowtoy, identity, radio

DEVICE_NAME = "feather-flowtoy-bridge"
FLOWTOY_BRIDGE_LOOP_INTERVAL_SECONDS = 0.02

IDENTITY = identity.Identity(
    device_name=DEVICE_NAME,
    firmware_commit=identity.default_firmware_commit(),
    device_id=device_id.persistent_device_id(),
    metadata={"protocol": radio.FLOWTOY_PROTOCOL, "mode": "receive-only"},
)


def respond_to_identify_query(*, stdin=None, print_fn=print) -> bool:
    """Process any pending Identify query from the host runtime."""

    return identity.poll_and_respond(IDENTITY, stdin=stdin, print_fn=print_fn)


def _write_serial_bus(message: str) -> None:
    """Emit a single newline-delimited message over the serial bridge."""

    print(message, end="")


def _default_packet() -> Mapping[str, object] | bytes | None:
    """Return no packet by default.

    Real hardware integrations should replace this with code that returns either
    a raw payload byte sequence or a mapping containing packet fields such as
    ``payload``, ``crc_ok``, ``rssi_dbm``, or ``metadata``.
    """

    return None


@dataclass
class RadioBridgeRuntime:
    """Coordinate packet acquisition and USB logging."""

    gather_packet: Callable[[], Mapping[str, object] | bytes | None] = _default_packet
    print_fn: Callable[[str], None] = print
    sleep_fn: Callable[[float], None] = time.sleep
    interval_seconds: float = FLOWTOY_BRIDGE_LOOP_INTERVAL_SECONDS
    match_flowtoy_schema: bool = True

    def _coerce_payload(self, packet: Mapping[str, object] | bytes) -> str | None:
        if isinstance(packet, Mapping) and "event_type" in packet and "data" in packet:
            return f"{json.dumps(packet)}\n"

        if isinstance(packet, Mapping):
            payload = self._extract_payload(packet)
            decoded = flowtoy.decode_if_matching(payload)
            if self.match_flowtoy_schema and decoded is None:
                return None
            metadata = packet.get("metadata")
            if metadata is not None and not isinstance(metadata, Mapping):
                raise TypeError("Radio packet metadata must be a mapping when provided")

            return radio.format_radio_packet_event(
                payload,
                protocol=str(packet.get("protocol", radio.FLOWTOY_PROTOCOL)),
                channel=int(packet.get("channel", radio.FLOWTOY_CHANNEL)),
                bitrate_kbps=int(packet.get("bitrate_kbps", radio.FLOWTOY_BITRATE_KBPS)),
                modulation=str(packet.get("modulation", radio.FLOWTOY_MODULATION)),
                crc_ok=self._extract_bool(packet.get("crc_ok")),
                frequency_hz=self._extract_optional_float(packet.get("frequency_hz")),
                rssi_dbm=self._extract_optional_float(packet.get("rssi_dbm")),
                decoded=decoded,
                metadata=metadata,
            )

        decoded = flowtoy.decode_if_matching(packet)
        if self.match_flowtoy_schema and decoded is None:
            return None
        return radio.format_radio_packet_event(packet)

    def _extract_payload(
        self,
        packet: Mapping[str, object],
    ) -> bytes | bytearray | memoryview | Sequence[int]:
        payload = packet.get("payload")
        if payload is None:
            raise ValueError("Radio packet mappings must include a payload")
        if isinstance(payload, (bytes, bytearray, memoryview, list, tuple)):
            return payload
        raise TypeError("Radio payloads must be bytes or integer sequences")

    def _extract_bool(self, value: object) -> bool | None:
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
            raise ValueError(f"Unable to parse boolean value from {value!r}")
        return bool(value)

    def _extract_optional_float(self, value: object) -> float | None:
        if value is None:
            return None
        return float(value)

    def run_once(self) -> None:
        respond_to_identify_query()
        packet = self.gather_packet()
        if packet is not None:
            rendered = self._coerce_payload(packet)
            if rendered is not None:
                self.print_fn(rendered)
        self.sleep_fn(self.interval_seconds)


def create_runtime(
    *,
    gather_packet_fn: Callable[[], Mapping[str, object] | bytes | None] = _default_packet,
    print_fn: Callable[[str], None] = _write_serial_bus,
    sleep_fn: Callable[[float], None] = time.sleep,
    interval_seconds: float = FLOWTOY_BRIDGE_LOOP_INTERVAL_SECONDS,
    match_flowtoy_schema: bool = True,
) -> RadioBridgeRuntime:
    """Create a FlowToy bridge runtime using the standard driver wiring."""

    return RadioBridgeRuntime(
        gather_packet=gather_packet_fn,
        print_fn=print_fn,
        sleep_fn=sleep_fn,
        interval_seconds=interval_seconds,
        match_flowtoy_schema=match_flowtoy_schema,
    )


def main(runtime: RadioBridgeRuntime | None = None) -> None:
    runtime = runtime or create_runtime()
    while True:
        runtime.run_once()


if __name__ == "__main__":  # pragma: no cover - executed on-device
    main()
