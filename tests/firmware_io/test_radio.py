from __future__ import annotations

import json

import pytest
from heart_firmware_io import constants, radio


class TestFirmwareIoRadio:
    """Validate firmware radio helpers so bridge payloads stay stable across board implementations."""

    def test_format_radio_packet_event_adds_decoded_flowtoy_payload(self) -> None:
        """Verify packet formatting enriches known FlowToy frames so downstream consumers get structure without losing the raw bytes."""
        rendered = radio.format_radio_packet_event(
            [
                0x00,
                0x01,
                0x02,
                0x00,
                0x00,
                0x00,
                0x01,
                0x02,
                0x03,
                0x04,
                10,
                20,
                30,
                40,
                50,
                0b0000_0011,
                0x00,
                0x00,
                2,
                7,
                0b0000_0010,
            ]
        )

        payload = json.loads(rendered[:-1])
        assert payload["data"]["decoded"]["schema"] == "flowtoy.sync.v1"
        assert payload["data"]["decoded"]["group_id"] == 1
        assert payload["data"]["decoded"]["page"] == 2
        assert payload["data"]["decoded"]["mode"] == 7

    def test_build_radio_packet_data_applies_flowtoy_defaults(self) -> None:
        """Verify packet helpers apply the shared FlowToy defaults so host parsing does not depend on board-specific ad hoc fields."""
        packet = radio.build_radio_packet_data(
            b"\x01\x02\xFF",
            crc_ok=True,
            metadata={"receiver": "feather"},
        )

        assert packet == {
            "protocol": "flowtoy",
            "channel": 2,
            "bitrate_kbps": 250,
            "modulation": "nrf24-shockburst",
            "crc_ok": True,
            "payload": [1, 2, 255],
            "metadata": {
                "address": [1, 7, 241],
                "address_width_bytes": 3,
                "crc_bits": 16,
                "receiver": "feather",
            },
        }

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            pytest.param(b"\x00\x10", [0, 16], id="bytes"),
            pytest.param([255, 256], [255, 0], id="sequence"),
        ],
    )
    def test_normalize_radio_payload_accepts_byte_sources(
        self,
        payload: object,
        expected: list[int],
    ) -> None:
        """Ensure payload normalization accepts byte-like inputs so firmware can serialize both raw buffers and parsed arrays."""
        assert radio.normalize_radio_payload(payload) == expected

    def test_format_radio_packet_event_emits_newline_delimited_json(self) -> None:
        """Verify event formatting produces the exact host framing so Totem can read packets line-by-line over USB serial."""
        rendered = radio.format_radio_packet_event([5, 6], crc_ok=False)

        assert rendered.endswith("\n")
        payload = json.loads(rendered[:-1])
        assert payload["event_type"] == constants.RADIO_PACKET
        assert payload["data"]["payload"] == [5, 6]
        assert payload["data"]["crc_ok"] is False
