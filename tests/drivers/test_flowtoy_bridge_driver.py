import io
import json

import driver_loader
from heart_firmware_io import constants


class TestDriversFlowtoyBridgeDriver:
    """Cover the FlowToy bridge harness so Feather-side packet forwarding stays compatible with Totem."""

    @staticmethod
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

    def test_runtime_emits_flowtoy_packet_schema(self, monkeypatch, tmp_path):
        """Verify the runtime emits the shared receive-only packet schema so host decoding stays stable across firmware revisions."""
        device_id_path = tmp_path / "device_id.txt"
        monkeypatch.setenv("HEART_DEVICE_ID_PATH", str(device_id_path))
        monkeypatch.setenv("HEART_DEVICE_ID", "flowtoy-bridge-test-id")
        flowtoy_bridge = driver_loader.load_driver_module("flowtoy_bridge")
        outputs: list[str] = []

        runtime = flowtoy_bridge.create_runtime(
            gather_packet_fn=lambda: {
                "payload": self._valid_sync_packet(),
                "crc_ok": True,
                "rssi_dbm": -47,
                "metadata": {"receiver": "feather"},
            },
            print_fn=outputs.append,
            sleep_fn=lambda _seconds: None,
            interval_seconds=0,
        )

        runtime.run_once()

        assert len(outputs) == 1
        payload = json.loads(outputs[0].rstrip("\n"))
        assert payload == {
            "event_type": constants.RADIO_PACKET,
            "data": {
                "protocol": "flowtoy",
                "channel": 2,
                "bitrate_kbps": 250,
                "modulation": "nrf24-shockburst",
                "crc_ok": True,
                "rssi_dbm": -47.0,
                "payload": list(self._valid_sync_packet()),
                "decoded": {
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
                    "reserved": [0, 0],
                    "page": 2,
                    "mode": 7,
                    "mode_name": "flowtoy-page-2-mode-7",
                    "mode_documentation": {
                        "page": 2,
                        "mode": 7,
                        "key": "flowtoy-page-2-mode-7",
                        "display_name": "unicorn",
                        "adjust": ["rainbow_brightness"],
                        "kinetic_trigger": ["low_force"],
                        "kinetic_response": ["activate_effect"],
                        "runtime": {
                            "static_hours": 9,
                            "kinetic_hours": 5,
                            "qualifier": "approx_plus",
                        },
                        "color_spectrum": [
                            {"t": 0.0, "hex": "#ffd6f6"},
                            {"t": 0.25, "hex": "#d9c2ff"},
                            {"t": 0.5, "hex": "#9be7ff"},
                            {"t": 0.75, "hex": "#b8ffd6"},
                            {"t": 1.0, "hex": "#fffdf7"},
                        ],
                        "source_url": "https://flowtoys2.freshdesk.com/support/solutions/articles/6000229509-capsule-v2-modes-adjust-kinetic-and-runtimes",
                    },
                    "command_flags": {
                        "adjust_active": False,
                        "wakeup": True,
                        "poweroff": False,
                        "force_reload": False,
                        "save": False,
                        "delete": False,
                        "alternate": False,
                    },
                },
                "metadata": {
                    "address": [1, 7, 241],
                    "address_width_bytes": 3,
                    "crc_bits": 16,
                    "receiver": "feather",
                },
            },
        }

    def test_runtime_skips_serial_output_when_no_packet_is_available(
        self,
        monkeypatch,
        tmp_path,
    ):
        """Verify the runtime stays quiet when the radio has nothing to report so idle links do not flood the host with empty frames."""
        device_id_path = tmp_path / "device_id.txt"
        monkeypatch.setenv("HEART_DEVICE_ID_PATH", str(device_id_path))
        monkeypatch.setenv("HEART_DEVICE_ID", "flowtoy-bridge-test-id")
        flowtoy_bridge = driver_loader.load_driver_module("flowtoy_bridge")
        outputs: list[str] = []

        runtime = flowtoy_bridge.create_runtime(
            gather_packet_fn=lambda: b"\x01\x02\x03",
            print_fn=outputs.append,
            sleep_fn=lambda _seconds: None,
            interval_seconds=0,
        )

        runtime.run_once()

        assert outputs == []

    def test_flowtoy_bridge_identify_query(self, monkeypatch, tmp_path):
        """Verify identify responses include the bridge metadata so operators can distinguish the receive-only FlowToy bridge from other Feather drivers."""
        device_id_path = tmp_path / "device_id.txt"
        monkeypatch.setenv("HEART_DEVICE_ID_PATH", str(device_id_path))
        monkeypatch.setenv("HEART_DEVICE_ID", "flowtoy-bridge-test-id")
        flowtoy_bridge = driver_loader.load_driver_module("flowtoy_bridge")
        outputs: list[str] = []

        handled = flowtoy_bridge.respond_to_identify_query(
            stdin=io.StringIO("Identify\n"),
            print_fn=outputs.append,
        )

        assert handled is True
        payload = json.loads(outputs[0])
        assert payload["event_type"] == constants.DEVICE_IDENTIFY
        assert payload["data"]["device_name"] == flowtoy_bridge.IDENTITY.device_name
        assert payload["data"]["device_id"] == "flowtoy-bridge-test-id"
        assert payload["data"]["protocol"] == "flowtoy"
        assert payload["data"]["mode"] == "receive-only"
