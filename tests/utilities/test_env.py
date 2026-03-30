"""Tests for :mod:`heart.utilities.env`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from heart.device.isolated_render import DEFAULT_SOCKET_PATH
from heart.utilities.env import (AssetCacheStrategy, BleUartBufferStrategy,
                                 Configuration, FrameExportStrategy,
                                 ReactivexStreamConnectMode, get_device_ports)


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



    def test_is_debug_mode_recognizes_truthy_tokens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure debug mode helper recognises canonical truthy tokens so feature flags behave reliably."""

        monkeypatch.setenv("DEBUG_MODE", " yes ")
        assert Configuration.is_debug_mode() is True

        monkeypatch.setenv("DEBUG_MODE", "false")
        assert Configuration.is_debug_mode() is False


    def test_asset_cache_strategy_defaults_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify asset cache strategy defaults to all. This keeps IO reuse enabled without explicit tuning."""
        _clear_env(monkeypatch, "HEART_ASSET_CACHE_STRATEGY")

        assert Configuration.asset_cache_strategy() == AssetCacheStrategy.ALL


    def test_asset_cache_strategy_rejects_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify asset cache strategy rejects invalid values. This keeps misconfiguration visible."""
        monkeypatch.setenv("HEART_ASSET_CACHE_STRATEGY", "nope")

        with pytest.raises(ValueError):
            Configuration.asset_cache_strategy()

    def test_asset_cache_strategy_accepts_images(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify asset cache strategy accepts images. This keeps image IO caching configurable."""
        monkeypatch.setenv("HEART_ASSET_CACHE_STRATEGY", "images")

        assert Configuration.asset_cache_strategy() == AssetCacheStrategy.IMAGES


    def test_ble_uart_buffer_strategy_defaults_bytes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify BLE UART buffer strategy defaults to bytes. This keeps IO parsing efficient by default."""
        _clear_env(monkeypatch, "HEART_BLE_UART_BUFFER_STRATEGY")

        assert Configuration.ble_uart_buffer_strategy() == BleUartBufferStrategy.BYTES


    def test_ble_uart_buffer_strategy_rejects_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify BLE UART buffer strategy rejects invalid values. This prevents ambiguous IO buffering."""
        monkeypatch.setenv("HEART_BLE_UART_BUFFER_STRATEGY", "nope")

        with pytest.raises(ValueError):
            Configuration.ble_uart_buffer_strategy()


    def test_asset_cache_max_entries_defaults_to_64(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify asset cache max entries defaults to 64. This provides bounded caching without extra config."""
        _clear_env(monkeypatch, "HEART_ASSET_CACHE_MAX_ENTRIES")

        assert Configuration.asset_cache_max_entries() == 64


    def test_asset_cache_max_entries_rejects_non_integer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify asset cache max entries rejects non-integers. This prevents ambiguous cache sizing."""
        monkeypatch.setenv("HEART_ASSET_CACHE_MAX_ENTRIES", "nope")

        with pytest.raises(ValueError):
            Configuration.asset_cache_max_entries()


    def test_asset_cache_max_entries_rejects_negative(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify asset cache max entries rejects negatives. This avoids undefined cache behaviour."""
        monkeypatch.setenv("HEART_ASSET_CACHE_MAX_ENTRIES", "-1")

        with pytest.raises(ValueError):
            Configuration.asset_cache_max_entries()


    def test_render_crash_on_error_defaults_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify renderer fail-fast defaults to disabled. This preserves the current production render-loop tolerance unless debugging is requested."""
        _clear_env(monkeypatch, "HEART_RENDER_CRASH_ON_ERROR")

        assert Configuration.render_crash_on_error() is False

    def test_render_crash_on_error_reads_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify renderer fail-fast reads the environment flag. This keeps crash-on-render-error debugging opt-in and explicit."""
        monkeypatch.setenv("HEART_RENDER_CRASH_ON_ERROR", "true")

        assert Configuration.render_crash_on_error() is True

    def test_random_seed_defaults_to_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the shared random seed defaults to None. This keeps project RNGs non-deterministic unless callers opt in."""
        _clear_env(monkeypatch, "HEART_RANDOM_SEED")

        assert Configuration.random_seed() is None

    def test_random_seed_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify the shared random seed reads the environment value. This keeps project-wide deterministic randomness configurable from one place."""
        monkeypatch.setenv("HEART_RANDOM_SEED", "123")

        assert Configuration.random_seed() == 123

    def test_frame_export_strategy_defaults_buffer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify frame export strategy defaults to buffer. This keeps frame conversion fast without extra config."""
        _clear_env(monkeypatch, "HEART_FRAME_EXPORT_STRATEGY")

        assert Configuration.frame_export_strategy() == FrameExportStrategy.BUFFER


    def test_frame_export_strategy_rejects_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify frame export strategy rejects invalid values. This prevents silent misconfiguration."""
        monkeypatch.setenv("HEART_FRAME_EXPORT_STRATEGY", "nope")

        with pytest.raises(ValueError):
            Configuration.frame_export_strategy()

    def test_reactivex_event_bus_scheduler_defaults_inline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the event bus scheduler defaults to inline so delivery stays predictable by default."""
        _clear_env(monkeypatch, "HEART_RX_EVENT_BUS_SCHEDULER")

        assert Configuration.reactivex_event_bus_scheduler() == "inline"


    def test_reactivex_event_bus_scheduler_rejects_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify invalid event bus scheduler values fail fast to keep configuration errors visible."""
        monkeypatch.setenv("HEART_RX_EVENT_BUS_SCHEDULER", "nope")

        with pytest.raises(ValueError):
            Configuration.reactivex_event_bus_scheduler()

    def test_reactivex_stream_refcount_grace_defaults_to_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify refcount grace defaults to zero so streams disconnect promptly unless tuned for churn."""
        _clear_env(monkeypatch, "HEART_RX_STREAM_REFCOUNT_GRACE_MS")

        assert Configuration.reactivex_stream_refcount_grace_ms() == 0

    def test_reactivex_stream_refcount_grace_reads_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify refcount grace reads the environment value so churn protection remains configurable."""
        monkeypatch.setenv("HEART_RX_STREAM_REFCOUNT_GRACE_MS", "25")

        assert Configuration.reactivex_stream_refcount_grace_ms() == 25

    def test_reactivex_stream_refcount_min_subscribers_defaults_to_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify refcount min subscribers defaults to one so share behaviour remains unchanged by default."""
        _clear_env(monkeypatch, "HEART_RX_STREAM_REFCOUNT_MIN_SUBSCRIBERS")

        assert Configuration.reactivex_stream_refcount_min_subscribers() == 1

    def test_reactivex_stream_refcount_min_subscribers_reads_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify refcount min subscribers reads the environment value so connection thresholds are configurable."""
        monkeypatch.setenv("HEART_RX_STREAM_REFCOUNT_MIN_SUBSCRIBERS", "2")

        assert Configuration.reactivex_stream_refcount_min_subscribers() == 2

    def test_reactivex_stream_connect_mode_defaults_lazy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify stream connect mode defaults to lazy to avoid missing immediate emissions."""
        _clear_env(monkeypatch, "HEART_RX_STREAM_CONNECT_MODE")

        assert (
            Configuration.reactivex_stream_connect_mode()
            == ReactivexStreamConnectMode.LAZY
        )

    def test_reactivex_stream_connect_mode_rejects_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify invalid stream connect modes fail fast to keep configuration errors visible."""
        monkeypatch.setenv("HEART_RX_STREAM_CONNECT_MODE", "nope")

        with pytest.raises(ValueError):
            Configuration.reactivex_stream_connect_mode()


    def test_get_device_ports_prefers_symlink_directory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that get device ports prefers symlink directory. This keeps connectivity configuration robust."""
        fake_entries = [
            Path("/dev/serial/by-id/ttyHeart-123"),
            Path("/dev/serial/by-id/other"),
        ]

        monkeypatch.setenv("ISOLATED_RENDER_HOST", "")  # ensure unrelated env noise is absent
        monkeypatch.setenv("ISOLATED_RENDER_PORT", "")

        monkeypatch.setattr("heart.utilities.env.ports.Path.exists", lambda self: True)
        monkeypatch.setattr(
            "heart.utilities.env.ports.Path.iterdir",
            lambda self: iter(fake_entries),
        )

        ports = list(get_device_ports("ttyHeart"))

        assert ports == ["/dev/serial/by-id/ttyHeart-123"]



    def test_get_device_ports_falls_back_when_directory_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that get device ports falls back when directory lacks matches to keep discovery resilient."""

        def fake_comports() -> Iterator[SimpleNamespace]:
            return iter(
                [
                    SimpleNamespace(device="/dev/cu.usbserial-0001", description="Heart Foo"),
                    SimpleNamespace(device="/dev/cu.Bluetooth-Incoming-Port", description="Other"),
                ]
            )

        monkeypatch.setattr("heart.utilities.env.ports.Path.exists", lambda self: True)
        monkeypatch.setattr(
            "heart.utilities.env.ports.Path.iterdir",
            lambda self: iter([Path("/dev/serial/by-id/other-device")]),
        )
        monkeypatch.setattr("heart.utilities.env.ports.platform.system", lambda: "Darwin")
        monkeypatch.setattr(
            "heart.utilities.env.ports.serial.tools.list_ports.comports",
            fake_comports,
        )

        ports = list(get_device_ports("heart"))

        assert ports == ["/dev/cu.usbserial-0001"]


    def test_get_device_ports_fallback_to_serial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that get device ports fallback to serial. This keeps connectivity configuration robust."""
        def fake_comports() -> Iterator[SimpleNamespace]:
            return iter(
                [
                    SimpleNamespace(device="/dev/cu.usbserial-0001", description="Heart Foo"),
                    SimpleNamespace(device="/dev/cu.Bluetooth-Incoming-Port", description="Other"),
                ]
            )

        monkeypatch.setattr("heart.utilities.env.ports.Path.exists", lambda self: False)

        monkeypatch.setattr("heart.utilities.env.ports.platform.system", lambda: "Darwin")
        monkeypatch.setattr(
            "heart.utilities.env.ports.serial.tools.list_ports.comports",
            fake_comports,
        )

        ports = list(get_device_ports("heart"))

        assert ports == ["/dev/cu.usbserial-0001"]
