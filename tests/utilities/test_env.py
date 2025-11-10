"""Tests for :mod:`heart.utilities.env`."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from heart.device.isolated_render import DEFAULT_SOCKET_PATH
from heart.utilities.env import Configuration, get_device_ports


@pytest.fixture(autouse=True)
def clear_is_pi_cache():
    """Ensure the cached Pi detection state does not leak between tests."""

    Configuration.is_pi.cache_clear()
    yield
    Configuration.is_pi.cache_clear()


def _clear_env(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    for name in names:
        monkeypatch.delenv(name, raising=False)


class TestUtilitiesEnv:
    """Group Utilities Env tests so utilities env behaviour stays reliable. This preserves confidence in utilities env for end-to-end scenarios."""

    def test_isolated_renderer_socket_prefers_explicit_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that isolated renderer socket prefers explicit path. This keeps rendering behaviour consistent across scenes."""
        monkeypatch.setenv("ISOLATED_RENDER_SOCKET", "/tmp/custom.sock")
        _clear_env(
            monkeypatch,
            "ISOLATED_RENDER_HOST",
            "ISOLATED_RENDER_PORT",
        )

        assert Configuration.isolated_renderer_socket() == "/tmp/custom.sock"



    def test_isolated_renderer_socket_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that isolated renderer socket empty string. This keeps rendering behaviour consistent across scenes."""
        monkeypatch.setenv("ISOLATED_RENDER_SOCKET", "")
        _clear_env(
            monkeypatch,
            "ISOLATED_RENDER_HOST",
            "ISOLATED_RENDER_PORT",
        )

        assert Configuration.isolated_renderer_socket() is None



    def test_isolated_renderer_socket_defaults_to_named_socket(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify that isolated renderer socket defaults to named socket. This keeps rendering behaviour consistent across scenes."""
        _clear_env(
            monkeypatch,
            "ISOLATED_RENDER_SOCKET",
            "ISOLATED_RENDER_HOST",
            "ISOLATED_RENDER_PORT",
        )

        assert Configuration.isolated_renderer_socket() == DEFAULT_SOCKET_PATH



    def test_isolated_renderer_socket_delegates_to_tcp_settings(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify that isolated renderer socket delegates to tcp settings. This keeps rendering behaviour consistent across scenes."""
        _clear_env(monkeypatch, "ISOLATED_RENDER_SOCKET")
        monkeypatch.setenv("ISOLATED_RENDER_HOST", "127.0.0.1")
        monkeypatch.setenv("ISOLATED_RENDER_PORT", "9000")

        assert Configuration.isolated_renderer_tcp_address() == ("127.0.0.1", 9000)
        assert Configuration.isolated_renderer_socket() is None



    def test_isolated_renderer_tcp_address_requires_both(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that isolated renderer tcp address requires both. This keeps rendering behaviour consistent across scenes."""
        monkeypatch.setenv("ISOLATED_RENDER_HOST", "127.0.0.1")
        monkeypatch.delenv("ISOLATED_RENDER_PORT", raising=False)

        with pytest.raises(ValueError):
            Configuration.isolated_renderer_tcp_address()

        monkeypatch.delenv("ISOLATED_RENDER_HOST", raising=False)
        monkeypatch.setenv("ISOLATED_RENDER_PORT", "8080")

        with pytest.raises(ValueError):
            Configuration.isolated_renderer_tcp_address()



    def test_isolated_renderer_tcp_address_requires_integer_port(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify that isolated renderer tcp address requires integer port. This keeps rendering behaviour consistent across scenes."""
        monkeypatch.setenv("ISOLATED_RENDER_HOST", "example.com")
        monkeypatch.setenv("ISOLATED_RENDER_PORT", "not-an-int")

        with pytest.raises(ValueError):
            Configuration.isolated_renderer_tcp_address()



    def test_isolated_renderer_tcp_address_returns_tuple(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that isolated renderer tcp address returns tuple. This keeps rendering behaviour consistent across scenes."""
        monkeypatch.setenv("ISOLATED_RENDER_HOST", "example.com")
        monkeypatch.setenv("ISOLATED_RENDER_PORT", "1234")

        assert Configuration.isolated_renderer_tcp_address() == ("example.com", 1234)



    def test_get_device_ports_prefers_symlink_directory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that get device ports prefers symlink directory. This keeps connectivity configuration robust."""
        fake_entries = ["ttyHeart-123", "other"]

        monkeypatch.setenv("ISOLATED_RENDER_HOST", "")  # ensure unrelated env noise is absent
        monkeypatch.setenv("ISOLATED_RENDER_PORT", "")

        monkeypatch.setattr("heart.utilities.env.os.path.exists", lambda path: True)
        monkeypatch.setattr("heart.utilities.env.os.listdir", lambda path: fake_entries)
        monkeypatch.setattr("heart.utilities.env.os.path.join", lambda a, b: f"{a}/{b}")

        ports = list(get_device_ports("ttyHeart"))

        assert ports == ["/dev/serial/by-id/ttyHeart-123"]



    def test_get_device_ports_fallback_to_serial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that get device ports fallback to serial. This keeps connectivity configuration robust."""
        def fake_comports() -> Iterator[SimpleNamespace]:
            return iter(
                [
                    SimpleNamespace(device="/dev/cu.usbserial-0001", description="Heart Foo"),
                    SimpleNamespace(device="/dev/cu.Bluetooth-Incoming-Port", description="Other"),
                ]
            )

        monkeypatch.setattr("heart.utilities.env.os.path.exists", lambda path: False)

        monkeypatch.setattr("heart.utilities.env.platform.system", lambda: "Darwin")
        monkeypatch.setattr(
            "heart.utilities.env.serial.tools.list_ports.comports",
            fake_comports,
        )

        ports = list(get_device_ports("heart"))

        assert ports == ["/dev/cu.usbserial-0001"]
