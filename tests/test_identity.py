import types

import pytest

from heart.firmware_io import identity


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv(identity.DEVICE_ID_ENV_VAR, raising=False)
    monkeypatch.delenv(identity.DEVICE_ID_PATH_ENV_VAR, raising=False)


class TestIdentity:
    """Group Identity tests so identity behaviour stays reliable. This preserves confidence in identity for end-to-end scenarios."""

    def test_persistent_device_id_reads_existing_file(self, tmp_path, monkeypatch):
        """Verify that persistent device id reads existing file. This ensures device provisioning workflows remain predictable."""
        storage_path = tmp_path / "device_id.txt"
        storage_path.write_text("existing-id")
        monkeypatch.setenv(identity.DEVICE_ID_PATH_ENV_VAR, str(storage_path))

        result = identity.persistent_device_id()

        assert result == "existing-id"



    def test_persistent_device_id_uses_env_and_persists(self, tmp_path, monkeypatch):
        """Verify that persistent device id uses env and persists. This ensures device provisioning workflows remain predictable."""
        storage_path = tmp_path / "device_id.txt"
        monkeypatch.setenv(identity.DEVICE_ID_PATH_ENV_VAR, str(storage_path))
        monkeypatch.setenv(identity.DEVICE_ID_ENV_VAR, "env-id-123")

        result = identity.persistent_device_id()

        assert result == "env-id-123"
        assert storage_path.read_text() == "env-id-123"



    def test_persistent_device_id_uses_hardware_uid(self, tmp_path, monkeypatch):
        """Verify that persistent device id uses hardware uid. This ensures device provisioning workflows remain predictable."""
        storage_path = tmp_path / "device_id.txt"
        monkeypatch.setenv(identity.DEVICE_ID_PATH_ENV_VAR, str(storage_path))

        stub_microcontroller = types.SimpleNamespace(cpu=types.SimpleNamespace(uid=b"\x01\xAB"))

        result = identity.persistent_device_id(microcontroller_module=stub_microcontroller)

        assert result == "01ab"
        assert storage_path.read_text() == "01ab"



    def test_persistent_device_id_generates_when_no_sources(self, tmp_path, monkeypatch):
        """Verify that persistent device id generates when no sources. This ensures device provisioning workflows remain predictable."""
        storage_path = tmp_path / "device_id.txt"
        monkeypatch.setenv(identity.DEVICE_ID_PATH_ENV_VAR, str(storage_path))
        monkeypatch.setattr(identity, "_hardware_device_uid", lambda _module=None: None)
        monkeypatch.setattr(identity, "_random_device_id", lambda: "feedbeef")

        result = identity.persistent_device_id()

        assert result == "feedbeef"
        assert storage_path.read_text() == "feedbeef"
