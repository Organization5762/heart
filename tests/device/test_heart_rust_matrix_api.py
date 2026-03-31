"""Tests for the Python-facing heart_rust matrix compatibility API."""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

HEART_RUST_PYTHON_PATH = (
    Path(__file__).resolve().parents[2] / "rust" / "heart_rust" / "python"
)


@dataclass(frozen=True)
class FakeNativeMatrixStats:
    """Carry fake runtime stats so the wrapper can mirror the native object shape."""

    width: int
    height: int
    dropped_frames: int
    rendered_frames: int
    refresh_hz_estimate: float
    backend_name: str


class FakeNativeMatrixDriver:
    """Capture wrapper calls so the compatibility API can be tested without native hardware."""

    def __init__(
        self,
        wiring: str,
        panel_rows: int,
        panel_cols: int,
        chain_length: int,
        parallel: int,
        color_order: str,
    ) -> None:
        self.wiring = wiring
        self.panel_rows = panel_rows
        self.panel_cols = panel_cols
        self.chain_length = chain_length
        self.parallel = parallel
        self.color_order = color_order
        self.submissions: list[tuple[bytes, int, int]] = []

    @property
    def width(self) -> int:
        return self.panel_cols * self.chain_length

    @property
    def height(self) -> int:
        return self.panel_rows * self.parallel

    def submit_rgba(self, data: bytes, width: int, height: int) -> None:
        self.submissions.append((data, width, height))

    def clear(self) -> None:
        self.submissions.append((b"", self.width, self.height))

    def stats(self) -> FakeNativeMatrixStats:
        return FakeNativeMatrixStats(
            width=self.width,
            height=self.height,
            dropped_frames=0,
            rendered_frames=len([data for data, _, _ in self.submissions if data]),
            refresh_hz_estimate=0.0,
            backend_name="fake",
        )

    def close(self) -> None:
        return None


class FakeColorOrder(Enum):
    RGB = "rgb"
    GBR = "gbr"


class FakeWiringProfile(Enum):
    AdafruitHatPwm = "adafruit_hat_pwm"
    AdafruitHat = "adafruit_hat"
    AdafruitTripleHat = "adafruit_triple_hat"


class TestHeartRustMatrixCompatibilityApi:
    """Validate the rgbmatrix-style wrapper so Python clients can reuse the common canvas flow without bypassing Rust."""

    def _load_heart_rust(self, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
        """Import the source tree package with a fake native backend so wrapper behavior stays isolated and deterministic."""

        for module_name in list(sys.modules):
            if module_name == "heart_rust" or module_name.startswith("heart_rust."):
                monkeypatch.delitem(sys.modules, module_name, raising=False)

        fake_native_module = ModuleType("heart_rust._heart_rust")
        fake_native_module.ColorOrder = FakeColorOrder
        fake_native_module.NativeMatrixDriver = FakeNativeMatrixDriver
        fake_native_module.NativeMatrixStats = FakeNativeMatrixStats
        fake_native_module.WiringProfile = FakeWiringProfile
        fake_native_module.SceneManagerBridge = object
        fake_native_module.SceneSnapshot = object
        fake_native_module.bridge_version = lambda: "0.1.0"

        monkeypatch.syspath_prepend(str(HEART_RUST_PYTHON_PATH))
        monkeypatch.setitem(sys.modules, "heart_rust._heart_rust", fake_native_module)
        return importlib.import_module("heart_rust")

    def test_frame_canvas_swaponvsync_submits_full_rgba_frame(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify CreateFrameCanvas plus SwapOnVSync reproduces the common offscreen-canvas flow. This matters because existing Python clients should be able to keep their draw-and-swap loop while still using the Rust runtime underneath."""

        heart_rust = self._load_heart_rust(monkeypatch)
        driver = heart_rust.MatrixDriver(
            heart_rust.MatrixConfig(
                wiring=heart_rust.WiringProfile.AdafruitHatPwm,
                panel_rows=16,
                panel_cols=32,
                chain_length=2,
                parallel=1,
                color_order=heart_rust.ColorOrder.RGB,
            )
        )

        offscreen = driver.CreateFrameCanvas()
        offscreen.Clear()
        offscreen.SetImage(Image.new("RGBA", (4, 3), (12, 34, 56, 255)), 2, 1)

        returned_canvas = driver.SwapOnVSync(offscreen)

        assert returned_canvas is offscreen
        native_driver = driver._driver
        assert len(native_driver.submissions) == 1
        submitted_bytes, width, height = native_driver.submissions[0]
        assert width == 64
        assert height == 16

        submitted_image = Image.frombytes("RGBA", (width, height), submitted_bytes)
        assert submitted_image.getpixel((0, 0)) == (0, 0, 0, 255)
        assert submitted_image.getpixel((2, 1)) == (12, 34, 56, 255)
        assert submitted_image.getpixel((5, 3)) == (12, 34, 56, 255)

    def test_frame_canvas_clear_resets_previous_pixels(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify FrameCanvas.Clear discards old image contents before the next swap. This matters because the common client loop depends on clearing the reusable offscreen buffer instead of allocating a fresh frame each render."""

        heart_rust = self._load_heart_rust(monkeypatch)
        driver = heart_rust.MatrixDriver(
            heart_rust.MatrixConfig(
                wiring=heart_rust.WiringProfile.AdafruitHatPwm,
                panel_rows=16,
                panel_cols=32,
                chain_length=1,
                parallel=1,
                color_order=heart_rust.ColorOrder.RGB,
            )
        )

        offscreen = driver.CreateFrameCanvas()
        offscreen.SetImage(Image.new("RGBA", (1, 1), (255, 0, 0, 255)), 0, 0)
        offscreen.Clear()

        driver.SwapOnVSync(offscreen)

        submitted_bytes, width, height = driver._driver.submissions[0]
        submitted_image = Image.frombytes("RGBA", (width, height), submitted_bytes)
        assert submitted_image.getpixel((0, 0)) == (0, 0, 0, 255)
