import types

import pytest

from heart.firmware_io import device_id


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv(device_id.DEVICE_ID_ENV_VAR, raising=False)
    monkeypatch.delenv(device_id.DEVICE_ID_PATH_ENV_VAR, raising=False)


class TestDeviceId:
    """Group device ID tests so persistence remains consistent. This preserves stable identification across deployments."""

    def test_persistent_device_id_reads_existing_file(self, tmp_path, monkeypatch):
        """Verify file-backed device IDs are reused to keep provisioning deterministic for operators."""
        storage_path = tmp_path / "device_id.txt"
        storage_path.write_text("existing-id", encoding="utf-8")
        monkeypatch.setenv(device_id.DEVICE_ID_PATH_ENV_VAR, str(storage_path))

        result = device_id.persistent_device_id()

        assert result == "existing-id"

    def test_persistent_device_id_uses_env_and_persists(self, tmp_path, monkeypatch):
        """Verify env-provided device IDs persist so later boots do not need external configuration."""
        storage_path = tmp_path / "device_id.txt"
        monkeypatch.setenv(device_id.DEVICE_ID_PATH_ENV_VAR, str(storage_path))
        monkeypatch.setenv(device_id.DEVICE_ID_ENV_VAR, "env-id-123")

        result = device_id.persistent_device_id()

        assert result == "env-id-123"
        assert storage_path.read_text(encoding="utf-8") == "env-id-123"

    def test_persistent_device_id_uses_hardware_uid(self, tmp_path, monkeypatch):
        """Verify hardware UIDs seed persistence so hardware boots align with fleet identity tracking."""
        storage_path = tmp_path / "device_id.txt"
        monkeypatch.setenv(device_id.DEVICE_ID_PATH_ENV_VAR, str(storage_path))

        stub_microcontroller = types.SimpleNamespace(cpu=types.SimpleNamespace(uid=b"\x01\xAB"))

        result = device_id.persistent_device_id(microcontroller_module=stub_microcontroller)

        assert result == "01ab"
        assert storage_path.read_text(encoding="utf-8") == "01ab"

    def test_persistent_device_id_generates_when_no_sources(self, tmp_path, monkeypatch):
        """Verify random IDs are generated as a fallback to keep devices identifiable in emergencies."""
        storage_path = tmp_path / "device_id.txt"
        monkeypatch.setenv(device_id.DEVICE_ID_PATH_ENV_VAR, str(storage_path))
        monkeypatch.setattr(device_id, "_hardware_device_uid", lambda _module=None: None)
        monkeypatch.setattr(device_id, "_random_device_id", lambda: "feedbeef")

        result = device_id.persistent_device_id()

        assert result == "feedbeef"
        assert storage_path.read_text(encoding="utf-8") == "feedbeef"
