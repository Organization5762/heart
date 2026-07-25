from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from heart.device.isolated_render import DEFAULT_SOCKET_PATH
from heart.utilities.env import (AssetCacheStrategy, BleUartBufferStrategy,
                                 Configuration, FrameExportStrategy,
                                 get_device_ports)


@pytest.fixture(autouse=True)
def clear_is_pi_cache():
    Configuration.is_pi.cache_clear()
    yield
    Configuration.is_pi.cache_clear()


def _clear_env(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    for name in names:
        monkeypatch.delenv(name, raising=False)


class TestUtilitiesEnv:
    def test_isolated_renderer_transport_is_explicit_and_validated(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        names = (
            "ISOLATED_RENDER_SOCKET",
            "ISOLATED_RENDER_HOST",
            "ISOLATED_RENDER_PORT",
        )
        _clear_env(monkeypatch, *names)
        assert Configuration.isolated_renderer_socket() == DEFAULT_SOCKET_PATH

        monkeypatch.setenv("ISOLATED_RENDER_SOCKET", "/tmp/custom.sock")
        assert Configuration.isolated_renderer_socket() == "/tmp/custom.sock"

        monkeypatch.setenv("ISOLATED_RENDER_SOCKET", "")
        assert Configuration.isolated_renderer_socket() is None

        monkeypatch.setenv("ISOLATED_RENDER_HOST", "example.com")
        monkeypatch.setenv("ISOLATED_RENDER_PORT", "1234")
        assert Configuration.isolated_renderer_tcp_address() == ("example.com", 1234)
        assert Configuration.isolated_renderer_socket() is None

        monkeypatch.delenv("ISOLATED_RENDER_PORT")
        with pytest.raises(ValueError):
            Configuration.isolated_renderer_tcp_address()

        monkeypatch.setenv("ISOLATED_RENDER_PORT", "not-an-int")
        with pytest.raises(ValueError):
            Configuration.isolated_renderer_tcp_address()

    def test_runtime_feature_flags_use_their_documented_names(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _clear_env(
            monkeypatch,
            "DEBUG_MODE",
            "FORWARD_TO_BEATS_APP",
            "FORWARD_TO_BEATS_MAP",
            "BEATS_WEBSOCKET_ENABLED",
        )
        assert Configuration.is_debug_mode() is False
        assert Configuration.forward_to_beats_app() is False
        assert Configuration.beats_websocket_enabled() is False

        monkeypatch.setenv("DEBUG_MODE", " yes ")
        monkeypatch.setenv("FORWARD_TO_BEATS_MAP", "true")
        monkeypatch.setenv("BEATS_WEBSOCKET_ENABLED", "true")
        assert Configuration.is_debug_mode() is True
        assert Configuration.forward_to_beats_app() is False
        assert Configuration.beats_websocket_enabled() is True

        monkeypatch.setenv("FORWARD_TO_BEATS_APP", "true")
        assert Configuration.forward_to_beats_app() is True

    def test_strategy_configuration_accepts_supported_values_and_rejects_others(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = (
            (
                "HEART_ASSET_CACHE_STRATEGY",
                Configuration.asset_cache_strategy,
                AssetCacheStrategy.ALL,
                "images",
                AssetCacheStrategy.IMAGES,
            ),
            (
                "HEART_BLE_UART_BUFFER_STRATEGY",
                Configuration.ble_uart_buffer_strategy,
                BleUartBufferStrategy.BYTES,
                "text",
                BleUartBufferStrategy.TEXT,
            ),
            (
                "HEART_FRAME_EXPORT_STRATEGY",
                Configuration.frame_export_strategy,
                FrameExportStrategy.BUFFER,
                "array",
                FrameExportStrategy.ARRAY,
            ),
        )
        for name, loader, default, configured, expected in settings:
            monkeypatch.delenv(name, raising=False)
            assert loader() == default
            monkeypatch.setenv(name, configured)
            assert loader() == expected
            monkeypatch.setenv(name, "unsupported")
            with pytest.raises(ValueError):
                loader()

    def test_numeric_configuration_has_safe_defaults_and_validation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _clear_env(monkeypatch, "HEART_ASSET_CACHE_MAX_ENTRIES", "HEART_RANDOM_SEED")
        assert Configuration.asset_cache_max_entries() == 64
        assert Configuration.random_seed() is None

        monkeypatch.setenv("HEART_ASSET_CACHE_MAX_ENTRIES", "0")
        monkeypatch.setenv("HEART_RANDOM_SEED", "123")
        assert Configuration.asset_cache_max_entries() == 0
        assert Configuration.random_seed() == 123

        for invalid in ("nope", "-1"):
            monkeypatch.setenv("HEART_ASSET_CACHE_MAX_ENTRIES", invalid)
            with pytest.raises(ValueError):
                Configuration.asset_cache_max_entries()

    def test_renderer_fail_fast_remains_opt_in(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("HEART_RENDER_CRASH_ON_ERROR", raising=False)
        assert Configuration.render_crash_on_error() is False
        monkeypatch.setenv("HEART_RENDER_CRASH_ON_ERROR", "true")
        assert Configuration.render_crash_on_error() is True

    def test_device_ports_prefer_stable_symlinks(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_entries = (
            Path("/dev/serial/by-id/ttyHeart-123"),
            Path("/dev/serial/by-id/other"),
        )
        monkeypatch.setattr("heart.utilities.env.ports.Path.exists", lambda self: True)
        monkeypatch.setattr(
            "heart.utilities.env.ports.Path.iterdir",
            lambda self: iter(fake_entries),
        )

        assert list(get_device_ports("ttyHeart")) == ["/dev/serial/by-id/ttyHeart-123"]

    def test_device_ports_fall_back_to_platform_serial_discovery(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_comports() -> Iterator[SimpleNamespace]:
            return iter(
                (
                    SimpleNamespace(
                        device="/dev/cu.usbserial-0001",
                        description="Heart Foo",
                    ),
                    SimpleNamespace(
                        device="/dev/cu.Bluetooth-Incoming-Port",
                        description="Other",
                    ),
                )
            )

        monkeypatch.setattr("heart.utilities.env.ports.Path.exists", lambda self: False)
        monkeypatch.setattr(
            "heart.utilities.env.ports.platform.system", lambda: "Darwin"
        )
        monkeypatch.setattr(
            "heart.utilities.env.ports.serial.tools.list_ports.comports",
            fake_comports,
        )

        assert list(get_device_ports("heart")) == ["/dev/cu.usbserial-0001"]
