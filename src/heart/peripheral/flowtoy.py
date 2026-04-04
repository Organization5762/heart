"""FlowToy-specific peripheral built on top of the radio bridge driver."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import Any

import reactivex
from reactivex.subject import Subject

from heart.peripheral.core import PeripheralInfo, PeripheralTag
from heart.peripheral.input_payloads import FlowToyPacket, RadioPacket
from heart.peripheral.radio import (RadioPeripheral, RawRadioPacket,
                                    SerialRadioDriver)
from heart.utilities.logging import get_logger

FLOWTOY_INPUT_VARIANT = "flowtoy"
FLOWTOY_PERIPHERAL_ID_PREFIX = "flowtoy"
PORT_SANITIZE_PATTERN = re.compile(r"[^a-zA-Z0-9]+")

logger = get_logger(__name__)


def _flowtoy_module() -> Any | None:
    """Return the optional FlowToy firmware helper module when available."""

    try:
        from heart_firmware_io import flowtoy
    except ImportError:
        logger.debug(
            "FlowToy firmware helpers are unavailable; using undecoded radio packets",
            exc_info=True,
        )
        return None
    return flowtoy


class FlowToyPeripheral(RadioPeripheral):
    """Expose FlowToy packets as a first-class peripheral stream."""

    EVENT_TYPE = FlowToyPacket.EVENT_TYPE

    def __init__(self, *, driver: SerialRadioDriver) -> None:
        super().__init__(driver=driver)
        self._packet_subject: Subject[FlowToyPacket] = Subject()

    @classmethod
    def detect(cls) -> Iterator["FlowToyPeripheral"]:
        for driver in SerialRadioDriver.detect():
            yield cls(driver=driver)

    def _event_stream(self) -> reactivex.Observable[FlowToyPacket]:
        return self._packet_subject

    def peripheral_info(self) -> PeripheralInfo:
        decoded = self._decoded_payload(self.latest_packet)
        flowtoy_module = _flowtoy_module()
        mode_name = (
            flowtoy_module.mode_name_from_decoded(decoded)
            if flowtoy_module is not None
            else "flowtoy-unknown"
        )
        tags = [
            PeripheralTag(name="input_variant", variant=FLOWTOY_INPUT_VARIANT),
            PeripheralTag(
                name="mode",
                variant=mode_name,
                metadata=self._mode_metadata(decoded),
            ),
        ]
        return PeripheralInfo(
            id=f"{self._base_id()}_{mode_name}",
            tags=tags,
        )

    def process_packet(self, packet: RawRadioPacket) -> None:
        if packet.protocol not in {None, "flowtoy"}:
            return

        decoded = self._decoded_payload(packet)
        if decoded is not None and packet.decoded is None:
            packet.decoded = decoded

        flowtoy_module = _flowtoy_module()
        mode_name = (
            flowtoy_module.mode_name_from_decoded(decoded)
            if flowtoy_module is not None
            else "flowtoy-unknown"
        )
        body = self._body_from_packet(packet)
        self._latest_packet = packet
        self._packet_subject.on_next(FlowToyPacket(body=body, mode_name=mode_name))

    def _base_id(self) -> str:
        port = getattr(self._driver, "port", None)
        if not isinstance(port, str) or not port:
            return FLOWTOY_PERIPHERAL_ID_PREFIX
        sanitized_port = PORT_SANITIZE_PATTERN.sub("_", port).strip("_").lower()
        if not sanitized_port:
            return FLOWTOY_PERIPHERAL_ID_PREFIX
        return f"{FLOWTOY_PERIPHERAL_ID_PREFIX}_{sanitized_port}"

    def _body_from_packet(self, packet: RawRadioPacket) -> dict[str, Any]:
        decoded = self._decoded_payload(packet)
        payload = RadioPacket(
            protocol=packet.protocol or "flowtoy",
            frequency_hz=packet.frequency_hz,
            channel=packet.channel,
            bitrate_kbps=packet.bitrate_kbps,
            modulation=packet.modulation,
            crc_ok=packet.crc_ok,
            rssi_dbm=packet.rssi_dbm,
            payload=packet.payload,
            decoded=decoded,
            metadata=packet.metadata,
        )
        return dict(payload.to_input().data)

    def _decoded_payload(
        self,
        packet: RawRadioPacket | None,
    ) -> Mapping[str, Any] | None:
        if packet is None:
            return None
        if packet.decoded is not None:
            return packet.decoded
        flowtoy_module = _flowtoy_module()
        if flowtoy_module is None:
            return None
        return flowtoy_module.decode_if_matching(packet.payload)

    def _mode_metadata(self, decoded: Mapping[str, Any] | None) -> dict[str, str]:
        if decoded is None:
            return {}

        metadata: dict[str, str] = {}
        for key in ("group_id", "page", "mode"):
            value = decoded.get(key)
            if value is None:
                continue
            metadata[key] = str(value)
        return metadata
