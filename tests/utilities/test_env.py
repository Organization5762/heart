"""Tests for :mod:`heart.utilities.env`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from heart.device.isolated_render import DEFAULT_SOCKET_PATH
from heart.utilities.env import (Configuration, ReactivexStreamConnectMode,
                                 RenderMergeStrategy, get_device_ports)


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


    def test_render_variant_defaults_iterative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that render variant defaults to iterative. This keeps render behaviour stable without explicit configuration."""
        _clear_env(monkeypatch, "HEART_RENDER_VARIANT")

        assert Configuration.render_variant() == "iterative"


    def test_render_parallel_threshold_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that render parallel threshold reads the environment value. This keeps tuning deterministic across deployments."""
        monkeypatch.setenv("HEART_RENDER_PARALLEL_THRESHOLD", "6")

        assert Configuration.render_parallel_threshold() == 6


    def test_render_executor_max_workers_returns_none_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that render executor max workers returns None when unset. This preserves default executor sizing."""
        _clear_env(monkeypatch, "HEART_RENDER_MAX_WORKERS")

        assert Configuration.render_executor_max_workers() is None


    def test_render_executor_max_workers_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that render executor max workers reads the environment value. This keeps parallelism caps configurable."""
        monkeypatch.setenv("HEART_RENDER_MAX_WORKERS", "3")

        assert Configuration.render_executor_max_workers() == 3


    def test_render_merge_strategy_defaults_batched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify render merge strategy defaults to batched. This keeps multi-renderer composition optimized without configuration."""
        _clear_env(monkeypatch, "HEART_RENDER_MERGE_STRATEGY")

        assert Configuration.render_merge_strategy() == RenderMergeStrategy.BATCHED


    def test_render_merge_strategy_rejects_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify render merge strategy rejects invalid values. This keeps configuration errors visible early."""
        monkeypatch.setenv("HEART_RENDER_MERGE_STRATEGY", "nope")

        with pytest.raises(ValueError):
            Configuration.render_merge_strategy()


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

        monkeypatch.setattr("heart.utilities.env.Path.exists", lambda self: True)
        monkeypatch.setattr(
            "heart.utilities.env.Path.iterdir",
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

        monkeypatch.setattr("heart.utilities.env.Path.exists", lambda self: True)
        monkeypatch.setattr(
            "heart.utilities.env.Path.iterdir",
            lambda self: iter([Path("/dev/serial/by-id/other-device")]),
        )
        monkeypatch.setattr("heart.utilities.env.platform.system", lambda: "Darwin")
        monkeypatch.setattr(
            "heart.utilities.env.serial.tools.list_ports.comports",
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

        monkeypatch.setattr("heart.utilities.env.Path.exists", lambda self: False)

        monkeypatch.setattr("heart.utilities.env.platform.system", lambda: "Darwin")
        monkeypatch.setattr(
            "heart.utilities.env.serial.tools.list_ports.comports",
            fake_comports,
        )

        ports = list(get_device_ports("heart"))

        assert ports == ["/dev/cu.usbserial-0001"]
