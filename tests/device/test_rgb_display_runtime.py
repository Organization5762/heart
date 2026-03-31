"""Tests for the clean-room HUB75 runtime integration."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pygame
import pytest

from heart.device import Rectangle
from heart.device.rgb_display.device import LEDMatrix
from heart.device.rgb_display.runtime import (build_matrix_config,
                                              build_matrix_driver)


@dataclass(frozen=True)
class FakeMatrixConfig:
    wiring: str
    panel_rows: int
    panel_cols: int
    chain_length: int
    parallel: int
    color_order: str


class FakeDriver:
    """Capture matrix-driver calls so Python integration stays testable without native hardware."""

    def __init__(self, config: FakeMatrixConfig) -> None:
        self.config = config
        self.closed = False
        self.submissions: list[tuple[bytes, int, int]] = []

    @property
    def width(self) -> int:
        return self.config.panel_cols * self.config.chain_length

    @property
    def height(self) -> int:
        return self.config.panel_rows * self.config.parallel

    def submit_rgba(self, data: bytes, width: int, height: int) -> None:
        self.submissions.append((data, width, height))

    def clear(self) -> None:
        pass

    def stats(self) -> object:
        return SimpleNamespace(
            width=self.width,
            height=self.height,
            dropped_frames=0,
            rendered_frames=len(self.submissions),
            refresh_hz_estimate=0.0,
            backend_name="fake",
        )

    def close(self) -> None:
        self.closed = True


class TestRgbDisplayRuntime:
    """Validate RGB display runtime hooks so the device path can move to the clean-room matrix API safely."""

    def test_build_matrix_config_uses_heart_geometry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify config translation keeps Heart panel geometry intact. This matters because the Rust runtime must receive the same logical layout the render pipeline already targets."""

        monkeypatch.setenv("HEART_PANEL_ROWS", "32")
        monkeypatch.setenv("HEART_PANEL_COLUMNS", "64")
        native_module = SimpleNamespace(
            MatrixConfig=FakeMatrixConfig,
            WiringProfile=SimpleNamespace(AdafruitHatPwm="hat-pwm"),
            ColorOrder=SimpleNamespace(RGB="rgb"),
        )

        config = build_matrix_config(native_module, Rectangle.with_layout(columns=2, rows=3))

        assert config == FakeMatrixConfig(
            wiring="hat-pwm",
            panel_rows=32,
            panel_cols=64,
            chain_length=2,
            parallel=3,
            color_order="rgb",
        )

    def test_build_matrix_driver_requires_native_runtime(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify driver construction fails clearly when the native package is unavailable. This matters because deployments need a direct signal that the clean-room runtime has not been installed."""

        monkeypatch.setattr(
            "heart.device.rgb_display.runtime.optional_import",
            lambda *_args, **_kwargs: None,
        )

        with pytest.raises(RuntimeError, match="clean-room HUB75 runtime is unavailable"):
            build_matrix_driver(Rectangle.with_layout(columns=1, rows=1))

    def test_build_matrix_driver_uses_native_public_api(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify driver creation flows through the reduced native API surface. This matters because the RGB device should stop depending on legacy rgbmatrix option objects."""

        fake_module = SimpleNamespace(
            MatrixConfig=FakeMatrixConfig,
            MatrixDriver=FakeDriver,
            WiringProfile=SimpleNamespace(AdafruitHatPwm="hat-pwm"),
            ColorOrder=SimpleNamespace(RGB="rgb"),
        )
        monkeypatch.setattr(
            "heart.device.rgb_display.runtime.optional_import",
            lambda *_args, **_kwargs: fake_module,
        )
        monkeypatch.setenv("HEART_PANEL_ROWS", "16")
        monkeypatch.setenv("HEART_PANEL_COLUMNS", "32")

        driver = build_matrix_driver(Rectangle.with_layout(columns=4, rows=1))

        assert isinstance(driver, FakeDriver)
        assert driver.config == FakeMatrixConfig(
            wiring="hat-pwm",
            panel_rows=16,
            panel_cols=32,
            chain_length=4,
            parallel=1,
            color_order="rgb",
        )

    def test_led_matrix_submits_rgba_surface_bytes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify LEDMatrix forwards raw RGBA bytes to the runtime. This matters because the production path should bypass the legacy offscreen canvas worker entirely."""

        fake_driver = FakeDriver(
            FakeMatrixConfig(
                wiring="hat-pwm",
                panel_rows=32,
                panel_cols=64,
                chain_length=1,
                parallel=1,
                color_order="rgb",
            )
        )
        monkeypatch.setenv("HEART_PANEL_ROWS", "32")
        monkeypatch.setenv("HEART_PANEL_COLUMNS", "64")
        monkeypatch.setattr(
            "heart.device.rgb_display.device.atexit.register",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            "heart.device.rgb_display.device.build_matrix_driver",
            lambda _orientation: fake_driver,
        )

        device = LEDMatrix(Rectangle.with_layout(columns=1, rows=1))
        surface = pygame.Surface((64, 32), flags=pygame.SRCALPHA)
        surface.fill((12, 34, 56, 255))

        device.set_screen(surface)

        assert len(fake_driver.submissions) == 1
        submitted_bytes, width, height = fake_driver.submissions[0]
        assert width == 64
        assert height == 32
        assert len(submitted_bytes) == 64 * 32 * 4

    def test_led_matrix_close_closes_driver(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify LEDMatrix shutdown closes the runtime driver. This matters because the Rust worker owns background state and must tear down cleanly on exit."""

        fake_driver = FakeDriver(
            FakeMatrixConfig(
                wiring="hat-pwm",
                panel_rows=64,
                panel_cols=64,
                chain_length=1,
                parallel=1,
                color_order="rgb",
            )
        )
        monkeypatch.setattr(
            "heart.device.rgb_display.device.atexit.register",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            "heart.device.rgb_display.device.build_matrix_driver",
            lambda _orientation: fake_driver,
        )

        device = LEDMatrix(Rectangle.with_layout(columns=1, rows=1))
        device.close()

        assert fake_driver.closed is True
