"""FlowToy-specific peripheral built on top of the radio bridge driver."""

from __future__ import annotations

import re
import time
from collections.abc import Iterator, Mapping
from typing import Any

from manyfold import StreamNode

from heart.peripheral.core import Input, PeripheralInfo, PeripheralTag
from heart.peripheral.core.input.color import ColorSnapshot
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.streams import EventStream
from heart.peripheral.core.subscriptions import NoopSubscription
from heart.peripheral.input_payloads import FlowToyPacket, RadioPacket
from heart.peripheral.radio import (FLOWTOY_PATTERN_EVENT, RadioPeripheral,
                                    RawRadioPacket, SerialRadioDriver)
from heart.utilities.logging import get_logger

FLOWTOY_INPUT_VARIANT = "flowtoy"
FLOWTOY_PERIPHERAL_ID_PREFIX = "flowtoy"
PORT_SANITIZE_PATTERN = re.compile(r"[^a-zA-Z0-9]+")
FLOWTOY_COLOR_ACTIVE_FLAGS = 0b0000_1110

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
        self._packet_stream: EventStream[FlowToyPacket] = EventStream()

    @classmethod
    def detect(cls) -> Iterator["FlowToyPeripheral"]:
        for driver in SerialRadioDriver.detect():
            yield cls(driver=driver)

    def _event_stream(self) -> StreamNode[FlowToyPacket]:
        return self._packet_stream.observable()

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
        self._packet_stream.emit(FlowToyPacket(body=body, mode_name=mode_name))

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


def bind_flowtoy_color_control(
    peripheral_manager: PeripheralManager,
    *,
    group_id: int = 0,
    group_is_public: bool = False,
    page: int = 0,
    mode: int = 0,
    min_interval_s: float = 0.25,
    rgb_delta: int = 8,
) -> Any:
    """Bind final-frame color snapshots to FlowToy pattern commands."""

    if not any(
        isinstance(peripheral, RadioPeripheral)
        for peripheral in peripheral_manager.peripherals
    ):
        return NoopSubscription()

    last_sent_at = 0.0
    last_rgb: tuple[int, int, int] | None = None

    def mapper(snapshot: ColorSnapshot) -> Input | None:
        nonlocal last_rgb, last_sent_at
        rgb = tuple(int(component) for component in snapshot.average_rgb)
        now = time.monotonic()
        if last_rgb is not None:
            delta = max(abs(left - right) for left, right in zip(rgb, last_rgb))
            if delta < rgb_delta:
                return None
            if now - last_sent_at < min_interval_s:
                return None
        last_rgb = rgb
        last_sent_at = now
        return Input(
            event_type=FLOWTOY_PATTERN_EVENT,
            data={
                "group_id": int(group_id),
                "group_is_public": bool(group_is_public),
                "page": int(page),
                "mode": int(mode),
                "actives": FLOWTOY_COLOR_ACTIVE_FLAGS,
                "hue_offset": _flowtoy_byte(snapshot.hue),
                "saturation": _flowtoy_byte(snapshot.saturation),
                "brightness": _flowtoy_byte(snapshot.brightness),
            },
        )

    return peripheral_manager.input_io.peripheral_inputs.bind(
        peripheral_manager.input_io.color.snapshot(),
        mapper,
        target=lambda peripheral: isinstance(peripheral, RadioPeripheral),
    )


def _flowtoy_byte(value: float) -> int:
    return max(0, min(255, int(round(float(value) * 255.0))))
