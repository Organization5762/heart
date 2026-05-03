from pathlib import Path

import pytest
from heart_device_manager.driver_update.configuration import load_driver_config
from heart_device_manager.driver_update.exceptions import UpdateError
from heart_device_manager.driver_update.modes import UpdateMode


class TestDriverUpdateConfiguration:
    """Cover driver update configuration parsing so automatic flashing modes remain explicit and safe across driver types."""

    def test_load_driver_config_parses_arduino_metadata(self, tmp_path: Path):
        """Verify Arduino-capable drivers parse native flashing metadata so the updater can compile and upload the right sketch automatically."""
        sketch_path = tmp_path / "arduino" / "example"
        sketch_path.mkdir(parents=True)
        settings_path = tmp_path / "settings.toml"
        settings_path.write_text(
            '\n'.join(
                [
                    'ARDUINO_BOARD_MANAGER_URLS="https://example.invalid/package_index.json"',
                    'ARDUINO_CORE="adafruit:nrf52"',
                    'ARDUINO_FQBN="adafruit:nrf52:feather52840"',
                    'ARDUINO_LIBRARIES="nrf_to_nrf"',
                    'ARDUINO_PORT_KEYWORDS="feather,nrf52840"',
                    'ARDUINO_SKETCH_PATH="arduino/example"',
                    'CIRCUIT_PY_BOOT_NAME="BOOT"',
                    'CIRCUIT_PY_DRIVER_LIBS=""',
                    'CIRCUIT_PY_UF2_CHECKSUM="checksum"',
                    'CIRCUIT_PY_UF2_URL="https://example.invalid/driver.uf2"',
                    'DEFAULT_UPDATE_MODE="arduino"',
                    'VALID_BOARD_IDS="feather_nrf52840_express"',
                ]
            ),
            encoding="utf-8",
        )

        config = load_driver_config(settings_path)

        assert config.default_update_mode == UpdateMode.ARDUINO
        assert config.arduino is not None
        assert config.arduino.core == "adafruit:nrf52"
        assert config.arduino.fqbn == "adafruit:nrf52:feather52840"
        assert config.arduino.libraries == ["nrf_to_nrf"]
        assert config.arduino.port_keywords == ["feather", "nrf52840"]
        assert config.arduino.sketch_path == sketch_path.resolve()

    def test_load_driver_config_rejects_arduino_default_without_sketch(
        self, tmp_path: Path
    ):
        """Verify Arduino default mode requires sketch metadata so auto mode cannot silently select a flashing path with no firmware to build."""
        settings_path = tmp_path / "settings.toml"
        settings_path.write_text(
            '\n'.join(
                [
                    'CIRCUIT_PY_BOOT_NAME="BOOT"',
                    'CIRCUIT_PY_DRIVER_LIBS=""',
                    'CIRCUIT_PY_UF2_CHECKSUM="checksum"',
                    'CIRCUIT_PY_UF2_URL="https://example.invalid/driver.uf2"',
                    'DEFAULT_UPDATE_MODE="arduino"',
                    'VALID_BOARD_IDS="feather_nrf52840_express"',
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(
            UpdateError, match="DEFAULT_UPDATE_MODE is arduino but no Arduino sketch"
        ):
            load_driver_config(settings_path)
