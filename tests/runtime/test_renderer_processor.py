"""Validate renderer processor telemetry."""

from __future__ import annotations

import pygame
import pytest

from heart import DeviceDisplayMode
from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering import renderer_processor
from heart.runtime.rendering.renderer_processor import RendererProcessor


class _StubRenderer:
    def __init__(self) -> None:
        self.name = "ExampleRenderer"
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def is_initialized(self) -> bool:
        return True


class _StubLogController:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def log(self, **kwargs: object) -> bool:
        self.calls.append(kwargs)
        return True


class TestRendererProcessor:
    """Ensure renderer processor metrics stay actionable so runtime throughput problems can be diagnosed from logs."""

    def test_log_renderer_metrics_includes_fps_estimate(
        self,
        device: Device,
        manager: PeripheralManager,
        monkeypatch,
    ) -> None:
        """Verify renderer loop logs include an FPS estimate so operators can gauge throughput without manually inverting frame times."""
        display_context = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        processor = RendererProcessor(display_context, manager)
        processor.set_queue_depth(3)
        processor.timing_tracker.record("ExampleRenderer", 20.0)

        stub_log_controller = _StubLogController()
        monkeypatch.setattr(
            renderer_processor,
            "log_controller",
            stub_log_controller,
        )
        renderer = _StubRenderer()

        processor._log_renderer_metrics(renderer, 20.0)

        assert stub_log_controller.calls
        log_call = stub_log_controller.calls[-1]
        assert log_call["key"] == "render.loop"
        assert "fps_estimate=%s" in log_call["msg"]
        assert log_call["extra"]["fps_estimate"] == 50.0

    def test_process_renderer_returns_none_when_fail_fast_disabled(
        self,
        device: Device,
        manager: PeripheralManager,
        monkeypatch,
    ) -> None:
        """Verify renderer exceptions stay non-fatal by default so one bad renderer does not stop the loop in normal operation."""
        display_context = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        processor = RendererProcessor(display_context, manager)
        renderer = _StubRenderer()

        monkeypatch.setenv("HEART_RENDER_CRASH_ON_ERROR", "false")
        monkeypatch.setattr(
            processor,
            "_render_frame_using_renderer",
            lambda _renderer: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        assert processor.process_renderer(renderer) is None

    def test_process_renderer_reraises_when_fail_fast_enabled(
        self,
        device: Device,
        manager: PeripheralManager,
        monkeypatch,
    ) -> None:
        """Verify renderer exceptions re-raise when fail-fast is enabled so debugging surfaces the original fault immediately."""
        display_context = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        processor = RendererProcessor(display_context, manager)
        renderer = _StubRenderer()

        monkeypatch.setenv("HEART_RENDER_CRASH_ON_ERROR", "true")
        monkeypatch.setattr(
            processor,
            "_render_frame_using_renderer",
            lambda _renderer: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        with pytest.raises(RuntimeError, match="boom"):
            processor.process_renderer(renderer)
