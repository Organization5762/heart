from __future__ import annotations

from heart_firmware_io import flowtoy


def _valid_sync_packet() -> bytes:
    return bytes(
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


class TestFirmwareIoFlowToy:
    """Validate FlowToy packet recognition so the radio bridge only forwards plausible payloads."""

    def test_decode_if_matching_recognizes_sync_packet_shape(self) -> None:
        """Verify the decoder recognizes the known sync packet shape so candidate captures can be filtered before reaching Totem."""
        decoded = flowtoy.decode_if_matching(_valid_sync_packet())

        assert decoded == {
            "schema": "flowtoy.sync.v1",
            "group_id": 1,
            "padding": 2,
            "lfo": [1, 2, 3, 4],
            "global": {
                "hue": 10,
                "saturation": 20,
                "brightness": 30,
                "speed": 40,
                "density": 50,
            },
            "active_flags": {
                "lfo": True,
                "hue": True,
                "saturation": False,
                "brightness": False,
                "speed": False,
                "density": False,
            },
            "page": 2,
            "mode": 7,
            "command_flags": {
                "adjust_active": False,
                "wakeup": True,
                "poweroff": False,
                "force_reload": False,
                "save": False,
                "delete": False,
                "alternate": False,
            },
        }

    def test_decode_if_matching_rejects_non_matching_payload(self) -> None:
        """Ensure non-matching candidate payloads are rejected so random 2.4 GHz traffic does not masquerade as FlowToy frames."""
        assert flowtoy.decode_if_matching(b"\x01\x02\x03") is None
