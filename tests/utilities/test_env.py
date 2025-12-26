"""Tests for :mod:`heart.utilities.env`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from heart.device.isolated_render import DEFAULT_SOCKET_PATH
from heart.utilities.env import (AssetCacheStrategy, BleUartBufferStrategy,
                                 Configuration, FrameExportStrategy,
                                 ReactivexStreamConnectMode,
                                 RenderLoopPacingStrategy, RenderMergeStrategy,
                                 RenderPlanSignatureStrategy, get_device_ports)


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


    def test_render_parallel_threshold_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that render parallel threshold reads the environment value. This keeps tuning deterministic across deployments."""
        monkeypatch.setenv("HEART_RENDER_PARALLEL_THRESHOLD", "6")

        assert Configuration.render_parallel_threshold() == 6

    def test_render_plan_signature_strategy_defaults_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify render plan signature strategy defaults to instance. This keeps caching behavior aligned with per-renderer timing."""
        _clear_env(monkeypatch, "HEART_RENDER_PLAN_SIGNATURE_STRATEGY")

        assert (
            Configuration.render_plan_signature_strategy()
            == RenderPlanSignatureStrategy.INSTANCE
        )

    def test_render_plan_signature_strategy_rejects_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify render plan signature strategy rejects invalid values. This prevents ambiguous render-plan caching."""
        monkeypatch.setenv("HEART_RENDER_PLAN_SIGNATURE_STRATEGY", "nope")

        with pytest.raises(ValueError):
            Configuration.render_plan_signature_strategy()


    def test_render_parallel_cost_threshold_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify render parallel cost threshold defaults. This keeps adaptive tuning predictable without extra configuration."""
        _clear_env(monkeypatch, "HEART_RENDER_PARALLEL_COST_THRESHOLD_MS")

        assert Configuration.render_parallel_cost_threshold_ms() == 12


    def test_render_parallel_cost_threshold_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify render parallel cost threshold reads the environment value. This keeps adaptive render tuning explicit."""
        monkeypatch.setenv("HEART_RENDER_PARALLEL_COST_THRESHOLD_MS", "18")

        assert Configuration.render_parallel_cost_threshold_ms() == 18

    def test_render_loop_pacing_strategy_defaults_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify render loop pacing strategy defaults to off. This avoids unexpected throttling without explicit configuration."""
        _clear_env(monkeypatch, "HEART_RENDER_LOOP_PACING_STRATEGY")

        assert (
            Configuration.render_loop_pacing_strategy()
            == RenderLoopPacingStrategy.OFF
        )

    def test_render_loop_pacing_strategy_rejects_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify render loop pacing strategy rejects invalid values. This keeps pacing configuration explicit."""
        monkeypatch.setenv("HEART_RENDER_LOOP_PACING_STRATEGY", "nope")

        with pytest.raises(ValueError):
            Configuration.render_loop_pacing_strategy()

    def test_render_loop_pacing_utilization_reads_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify render loop pacing utilization reads environment value. This keeps throttling targets configurable."""
        monkeypatch.setenv("HEART_RENDER_LOOP_PACING_UTILIZATION", "0.75")

        assert Configuration.render_loop_pacing_utilization() == 0.75


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


    def test_render_merge_strategy_defaults_batched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify render merge strategy defaults to batched. This keeps multi-renderer composition optimized without configuration."""
        _clear_env(monkeypatch, "HEART_RENDER_MERGE_STRATEGY")

        assert Configuration.render_merge_strategy() == RenderMergeStrategy.BATCHED


    def test_render_merge_strategy_accepts_adaptive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify render merge strategy accepts adaptive mode. This keeps runtime tuning flexible for composition overhead."""
        monkeypatch.setenv("HEART_RENDER_MERGE_STRATEGY", "adaptive")

        assert Configuration.render_merge_strategy() == RenderMergeStrategy.ADAPTIVE


    def test_render_merge_strategy_rejects_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify render merge strategy rejects invalid values. This keeps configuration errors visible early."""
        monkeypatch.setenv("HEART_RENDER_MERGE_STRATEGY", "nope")

        with pytest.raises(ValueError):
            Configuration.render_merge_strategy()


    def test_render_merge_cost_threshold_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify render merge cost threshold reads the environment value. This keeps adaptive merge tuning configurable."""
        monkeypatch.setenv("HEART_RENDER_MERGE_COST_THRESHOLD_MS", "9")

        assert Configuration.render_merge_cost_threshold_ms() == 9


    def test_render_merge_surface_threshold_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify render merge surface threshold reads the environment value. This keeps adaptive merge decisions consistent."""
        monkeypatch.setenv("HEART_RENDER_MERGE_SURFACE_THRESHOLD", "5")

        assert Configuration.render_merge_surface_threshold() == 5


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
