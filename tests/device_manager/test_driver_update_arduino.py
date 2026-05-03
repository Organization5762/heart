from pathlib import Path
from types import SimpleNamespace

import pytest
from heart_device_manager.driver_update.arduino import (resolve_arduino_port,
                                                        update_arduino_sketch)
from heart_device_manager.driver_update.configuration import (ArduinoConfig,
                                                              DriverConfig)
from heart_device_manager.driver_update.exceptions import UpdateError
from heart_device_manager.driver_update.modes import UpdateMode


class TestDriverUpdateArduino:
    """Cover Arduino-native driver updates so Feather firmware flashing stays automated and predictable."""

    def _config(self, tmp_path: Path) -> DriverConfig:
        sketch_path = tmp_path / "sketch"
        sketch_path.mkdir()
        return DriverConfig(
            uf2_url="https://example.invalid/driver.uf2",
            uf2_checksum="checksum",
            driver_libs=[],
            device_boot_name="FTHR840BOOT",
            valid_board_ids=["feather_nrf52840_express"],
            default_update_mode=UpdateMode.ARDUINO,
            arduino=ArduinoConfig(
                board_manager_urls=[
                    "https://adafruit.github.io/arduino-board-index/package_adafruit_index.json"
                ],
                core="adafruit:nrf52",
                fqbn="adafruit:nrf52:feather52840",
                libraries=["nrf_to_nrf"],
                port_keywords=["feather", "nrf52840"],
                sketch_path=sketch_path,
            ),
        )

    def test_update_arduino_sketch_runs_expected_cli_commands(
        self, monkeypatch, tmp_path
    ):
        """Verify Arduino updates install dependencies, compile, and upload in order so a single driver command can fully provision the Feather."""
        config = self._config(tmp_path)
        commands: list[list[str]] = []

        monkeypatch.setattr(
            "heart_device_manager.driver_update.arduino._resolve_arduino_cli_binary",
            lambda: "arduino-cli",
        )
        monkeypatch.setattr(
            "heart_device_manager.driver_update.arduino.resolve_arduino_port",
            lambda _config: "/dev/cu.usbmodemFLOWTOY1",
        )
        monkeypatch.setattr(
            "heart_device_manager.driver_update.arduino._run_arduino_cli",
            commands.append,
        )

        update_arduino_sketch(config)

        prefix = [
            "arduino-cli",
            "--additional-urls",
            "https://adafruit.github.io/arduino-board-index/package_adafruit_index.json",
        ]
        assert commands == [
            prefix + ["core", "update-index"],
            prefix + ["core", "install", "adafruit:nrf52"],
            prefix + ["lib", "install", "nrf_to_nrf"],
            prefix
            + [
                "compile",
                "--fqbn",
                "adafruit:nrf52:feather52840",
                str(config.arduino.sketch_path),
            ],
            prefix
            + [
                "upload",
                "--fqbn",
                "adafruit:nrf52:feather52840",
                "--port",
                "/dev/cu.usbmodemFLOWTOY1",
                "--verify",
                str(config.arduino.sketch_path),
            ],
        ]

    def test_resolve_arduino_port_prefers_highest_keyword_match(self, monkeypatch):
        """Verify Arduino port resolution picks the best keyword match so uploads target the intended Feather when multiple serial devices are attached."""
        monkeypatch.setattr(
            "heart_device_manager.driver_update.arduino.serial.tools.list_ports.comports",
            lambda: [
                SimpleNamespace(
                    device="/dev/cu.other",
                    description="Other Serial Device",
                    manufacturer="Acme",
                    product="Debugger",
                    hwid="foo",
                ),
                SimpleNamespace(
                    device="/dev/cu.feather",
                    description="Adafruit Feather nRF52840 Express",
                    manufacturer="Adafruit",
                    product="Feather nRF52840 Express",
                    hwid="bar",
                ),
            ],
        )

        port = resolve_arduino_port(
            ArduinoConfig(
                board_manager_urls=[],
                core="adafruit:nrf52",
                fqbn="adafruit:nrf52:feather52840",
                libraries=[],
                port_keywords=["feather", "nrf52840"],
                sketch_path=Path("/tmp/sketch"),
            )
        )

        assert port == "/dev/cu.feather"

    def test_resolve_arduino_port_rejects_ambiguous_matches(self, monkeypatch):
        """Verify Arduino port resolution fails on tied matches so the updater does not flash the wrong Feather when discovery is ambiguous."""
        monkeypatch.setattr(
            "heart_device_manager.driver_update.arduino.serial.tools.list_ports.comports",
            lambda: [
                SimpleNamespace(
                    device="/dev/cu.feather-a",
                    description="Feather nRF52840 Express A",
                    manufacturer="Adafruit",
                    product="Feather",
                    hwid="foo",
                ),
                SimpleNamespace(
                    device="/dev/cu.feather-b",
                    description="Feather nRF52840 Express B",
                    manufacturer="Adafruit",
                    product="Feather",
                    hwid="bar",
                ),
            ],
        )

        with pytest.raises(UpdateError, match="Multiple Arduino upload ports matched"):
            resolve_arduino_port(
                ArduinoConfig(
                    board_manager_urls=[],
                    core="adafruit:nrf52",
                    fqbn="adafruit:nrf52:feather52840",
                    libraries=[],
                    port_keywords=["feather", "nrf52840"],
                    sketch_path=Path("/tmp/sketch"),
                )
            )
