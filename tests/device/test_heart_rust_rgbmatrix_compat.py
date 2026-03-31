"""Tests for the opt-in heart_rust rgbmatrix compatibility layer."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from heart.device.rgb_display import heart_rust_rgbmatrix


@dataclass(frozen=True)
class FakeMatrixConfig:
    """Carry translated config values so compatibility tests can inspect native inputs directly."""

    wiring: object
    panel_rows: int
    panel_cols: int
    chain_length: int
    parallel: int
    color_order: object


class FakeNativeMatrixDriver:
    """Capture compatibility calls so the rgbmatrix wrapper can be exercised without native hardware."""

    def __init__(self, config: FakeMatrixConfig) -> None:
        self.config = config
        self.closed = False
        self.cleared = False
        self.canvas = object()
        self.swapped_canvases: list[object] = []

    @property
    def width(self) -> int:
        return self.config.panel_cols * self.config.chain_length

    @property
    def height(self) -> int:
        return self.config.panel_rows * self.config.parallel

    def CreateFrameCanvas(self) -> object:
        return self.canvas

    def SwapOnVSync(self, frame_canvas: object) -> object:
        self.swapped_canvases.append(frame_canvas)
        return frame_canvas

    def clear(self) -> None:
        self.cleared = True

    def stats(self) -> object:
        return SimpleNamespace(backend_name="fake-heart-rust")

    def close(self) -> None:
        self.closed = True


class TestHeartRustRgbmatrixCompatibility:
    """Validate the separate heart_rust rgbmatrix shim so legacy-style callers can opt in without touching the real rgbmatrix import path."""

    @staticmethod
    def _fake_native_module() -> SimpleNamespace:
        return SimpleNamespace(
            MatrixConfig=FakeMatrixConfig,
            MatrixDriver=FakeNativeMatrixDriver,
            WiringProfile=SimpleNamespace(
                AdafruitHatPwm="hat-pwm",
                AdafruitHat="hat",
            ),
            ColorOrder=SimpleNamespace(RGB="rgb", GBR="gbr"),
        )

    def test_rgb_matrix_options_translate_supported_geometry_and_color(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the compatibility layer maps supported rgbmatrix options into the clean-room native config. This matters because migration code should keep its geometry and color-order intent when moving onto the heart_rust device stack."""

        fake_module = self._fake_native_module()
        monkeypatch.setattr(
            heart_rust_rgbmatrix,
            "_load_matrix_runtime_module",
            lambda: fake_module,
        )
        options = heart_rust_rgbmatrix.RGBMatrixOptions()
        options.hardware_mapping = "adafruit-hat"
        options.rows = 64
        options.cols = 64
        options.chain_length = 4
        options.parallel = 1
        options.led_rgb_sequence = "GBR"

        matrix = heart_rust_rgbmatrix.RGBMatrix(options=options)

        assert matrix._driver.config == FakeMatrixConfig(
            wiring="hat",
            panel_rows=64,
            panel_cols=64,
            chain_length=4,
            parallel=1,
            color_order="gbr",
        )
        assert matrix.width == 256
        assert matrix.height == 64

    def test_rgb_matrix_proxies_canvas_swap_and_clear(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the compatibility wrapper forwards the familiar canvas and clear calls to the native driver. This matters because existing draw loops should be able to reuse their CreateFrameCanvas/SwapOnVSync structure on top of heart_rust."""

        fake_module = self._fake_native_module()
        monkeypatch.setattr(
            heart_rust_rgbmatrix,
            "_load_matrix_runtime_module",
            lambda: fake_module,
        )
        matrix = heart_rust_rgbmatrix.RGBMatrix()

        canvas = matrix.CreateFrameCanvas()
        swapped_canvas = matrix.SwapOnVSync(canvas)
        matrix.Clear()

        assert canvas is matrix._driver.canvas
        assert swapped_canvas is canvas
        assert matrix._driver.swapped_canvases == [canvas]
        assert matrix._driver.cleared is True

    def test_rgb_matrix_rejects_unsupported_hardware_mapping(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify unsupported hardware mappings fail fast with a clear message. This matters because callers should learn immediately when they request an hzeller-specific transport shape the heart_rust stack does not implement."""

        fake_module = self._fake_native_module()
        monkeypatch.setattr(
            heart_rust_rgbmatrix,
            "_load_matrix_runtime_module",
            lambda: fake_module,
        )
        options = heart_rust_rgbmatrix.RGBMatrixOptions()
        options.hardware_mapping = "regular"

        with pytest.raises(ValueError, match="hardware mappings"):
            heart_rust_rgbmatrix.RGBMatrix(options=options)

    def test_rgb_matrix_warns_when_legacy_options_are_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify non-default legacy rgbmatrix knobs are logged as ignored. This matters because the compatibility layer should be honest about which options are still placeholders while the clean-room runtime grows feature coverage."""

        fake_module = self._fake_native_module()
        monkeypatch.setattr(
            heart_rust_rgbmatrix,
            "_load_matrix_runtime_module",
            lambda: fake_module,
        )
        options = heart_rust_rgbmatrix.RGBMatrixOptions()
        options.brightness = 50
        options.pwm_bits = 8
        warning_messages: list[str] = []
        monkeypatch.setattr(
            heart_rust_rgbmatrix.logger,
            "warning",
            lambda message, ignored_options: warning_messages.append(
                message % ignored_options
            ),
        )

        heart_rust_rgbmatrix.RGBMatrix(options=options)

        assert len(warning_messages) == 1
        assert "ignores legacy rgbmatrix options" in warning_messages[0]
        assert "brightness=50" in warning_messages[0]
        assert "pwm_bits=8" in warning_messages[0]
