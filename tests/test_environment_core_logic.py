"""Additional tests for runtime and color conversion helpers."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pygame
import pytest

from heart import DeviceDisplayMode
from heart.navigation import ComposedRenderer
from heart.utilities.color_conversion import (HSV_TO_BGR_CACHE,
                                              _convert_bgr_to_hsv,
                                              _convert_hsv_to_bgr)
from heart.utilities.env import Configuration


def _solid_surface(color: tuple[int, int, int]) -> pygame.Surface:
    surface = pygame.Surface((8, 8), pygame.SRCALPHA)
    surface.fill(color)
    return surface


@pytest.fixture(autouse=True)
def disable_cv2(monkeypatch):
    """Force the color conversion helpers to use the numpy fallbacks."""

    monkeypatch.setattr("heart.utilities.color_conversion.CV2_MODULE", None)


@pytest.fixture(autouse=True)
def clear_hsv_cache():
    """Ensure colour conversion cache state is isolated between tests."""

    HSV_TO_BGR_CACHE.clear()
    yield
    HSV_TO_BGR_CACHE.clear()


class TestEnvironmentCoreLogic:
    """Group runtime and color conversion tests so core behaviours stay reliable. This preserves confidence in render loop orchestration and color conversion accuracy."""

    @pytest.mark.parametrize(
        "bgr,expected",
        [
            (
                np.array([0, 0, 255], dtype=np.uint8),
                np.array([0, 255, 255], dtype=np.uint8),
            ),
            (
                np.array([0, 255, 0], dtype=np.uint8),
                np.array([60, 255, 255], dtype=np.uint8),
            ),
            (
                np.array([255, 0, 0], dtype=np.uint8),
                np.array([120, 255, 255], dtype=np.uint8),
            ),
            (np.array([50, 50, 50], dtype=np.uint8), np.array([0, 0, 50], dtype=np.uint8)),
        ],
    )
    def test_convert_bgr_to_hsv_known_colors(self, bgr: np.ndarray, expected: np.ndarray) -> None:
        """Verify that _convert_bgr_to_hsv maps canonical BGR inputs to expected HSV values. This keeps colour transforms dependable for renderer pipelines."""
        image = bgr.reshape(1, 1, 3)
        hsv = _convert_bgr_to_hsv(image)
        np.testing.assert_array_equal(hsv.reshape(3), expected)


    @pytest.mark.parametrize(
        "hsv,expected",
        [
            (
                np.array([0, 255, 255], dtype=np.uint8),
                np.array([0, 0, 255], dtype=np.uint8),
            ),
            (
                np.array([60, 255, 255], dtype=np.uint8),
                np.array([2, 255, 0], dtype=np.uint8),
            ),
            (
                np.array([119, 255, 255], dtype=np.uint8),
                np.array([255, 0, 5], dtype=np.uint8),
            ),
            (np.array([0, 0, 50], dtype=np.uint8), np.array([50, 50, 50], dtype=np.uint8)),
        ],
    )
    def test_convert_hsv_to_bgr_known_colors(self, hsv: np.ndarray, expected: np.ndarray) -> None:
        """Verify that _convert_hsv_to_bgr reproduces known BGR colours from HSV inputs. This prevents palette drift when using cached conversions."""
        image = hsv.reshape(1, 1, 3)
        bgr = _convert_hsv_to_bgr(image)
        np.testing.assert_array_equal(bgr.reshape(3), expected)



    @pytest.mark.parametrize("seed", [0, 1, 42])
    def test_color_round_trip(self, seed: int) -> None:
        """Verify that random BGR arrays survive a round trip through HSV conversion. This proves the helpers are lossless for display operations."""
        rng = np.random.default_rng(seed)
        bgr = rng.integers(0, 256, size=(4, 5, 3), dtype=np.uint8)

        hsv = _convert_bgr_to_hsv(bgr)
        round_trip = _convert_hsv_to_bgr(hsv)

        np.testing.assert_array_equal(round_trip, bgr)



    def test_convert_bgr_to_hsv_populates_cache_for_standard_values(self) -> None:
        """Verify that _convert_bgr_to_hsv populates the cache for standard values while skipping sentinel entries. This ensures repeated conversions stay fast without polluting special cases."""
        image = np.array(
            [[[10, 20, 30], [40, 60, 80], [0, 255, 0]]],
            dtype=np.uint8,
        )

        hsv = _convert_bgr_to_hsv(image)

        flat_bgr = image.reshape(-1, 3)
        flat_hsv = hsv.reshape(-1, 3)

        for hsv_value, bgr_value in zip(flat_hsv[:-1], flat_bgr[:-1]):
            key = tuple(int(x) for x in hsv_value)
            assert key in HSV_TO_BGR_CACHE
            np.testing.assert_array_equal(HSV_TO_BGR_CACHE[key], bgr_value)

        special_key = tuple(int(x) for x in flat_hsv[-1])
        assert special_key == (60, 255, 255)
        assert special_key not in HSV_TO_BGR_CACHE



    def test_convert_hsv_to_bgr_prefers_cached_values(self) -> None:
        """Verify that _convert_hsv_to_bgr prefers cached values when available. This keeps interactive rendering snappy by avoiding recomputation."""
        key = (12, 34, 200)
        cached_value = np.array([1, 2, 3], dtype=np.uint8)
        HSV_TO_BGR_CACHE[key] = cached_value.copy()

        hsv = np.array([[list(key)]], dtype=np.uint8)
        result = _convert_hsv_to_bgr(hsv)

        np.testing.assert_array_equal(result[0, 0], cached_value)
        assert next(reversed(HSV_TO_BGR_CACHE)) == key



    def test_convert_hsv_to_bgr_calibration_clears_cache_for_known_keys(self) -> None:
        """Verify that _convert_hsv_to_bgr clears cached values for calibration keys. This allows dynamic tuning without stale entries lingering."""
        key = (60, 255, 255)
        HSV_TO_BGR_CACHE[key] = np.array([9, 9, 9], dtype=np.uint8)

        hsv = np.array([[list(key)]], dtype=np.uint8)
        result = _convert_hsv_to_bgr(hsv)

        np.testing.assert_array_equal(result[0, 0], np.array([2, 255, 0], dtype=np.uint8))
        assert key not in HSV_TO_BGR_CACHE



    def test_render_batch_merges_surfaces_sequentially(self, loop, monkeypatch) -> None:
        """Verify that composed batch rendering layers child surfaces in order. This keeps the new single composition path visually stable when multiple renderers overlap."""
        renderers = [
            SimpleNamespace(name="r1", device_display_mode=DeviceDisplayMode.FULL),
            SimpleNamespace(name="r2", device_display_mode=DeviceDisplayMode.FULL),
        ]
        surfaces = {
            "r1": _solid_surface((255, 0, 0)),
            "r2": _solid_surface((0, 0, 255)),
        }

        monkeypatch.setattr(
            ComposedRenderer,
            "_render_renderer",
            staticmethod(lambda renderer, **_kwargs: surfaces[renderer.name]),
        )

        result = loop.render_frame(renderers)

        assert isinstance(result, pygame.Surface)
        assert result.get_at((0, 0))[:3] == (0, 0, 255)


    @pytest.mark.parametrize(
        "value,expected",
        [
            ("strict", "strict"),
            ("fast", "fast"),
            ("off", "off"),
        ],
        ids=["strict-mode", "fast-mode", "off-mode"],
    )
    def test_hsv_calibration_mode_env_override(
        self, monkeypatch, value: str, expected: str
    ) -> None:
        """Verify that hsv_calibration_mode reads explicit overrides. This keeps performance tuning consistent across deployments."""
        monkeypatch.setenv("HEART_HSV_CALIBRATION_MODE", value)
        assert Configuration.hsv_calibration_mode() == expected

    def test_render_frame_skips_renderer_errors_when_fail_fast_disabled(
        self, loop, monkeypatch
    ) -> None:
        """Verify that renderer failures are skipped by default in the shared composition path. This preserves the loop's tolerance for one bad renderer while keeping other visuals alive."""
        renderers = [
            SimpleNamespace(name="boom", device_display_mode=DeviceDisplayMode.FULL),
            SimpleNamespace(name="ok", device_display_mode=DeviceDisplayMode.FULL),
        ]

        def _render(renderer: SimpleNamespace, **_kwargs) -> pygame.Surface:
            if renderer.name == "boom":
                raise RuntimeError("boom")
            return _solid_surface((10, 20, 30))

        monkeypatch.setenv("HEART_RENDER_CRASH_ON_ERROR", "false")
        monkeypatch.setattr(
            ComposedRenderer,
            "_render_renderer",
            staticmethod(_render),
        )

        result = loop.render_frame(renderers)

        assert isinstance(result, pygame.Surface)
        assert result.get_at((0, 0))[:3] == (10, 20, 30)

    def test_render_frame_reraises_when_fail_fast_enabled(
        self, loop, monkeypatch
    ) -> None:
        """Verify that crash-on-render-error still propagates failures in the shared composition path. This keeps explicit debugging behaviour intact after removing the pipeline layer."""
        renderers = [
            SimpleNamespace(name="boom", device_display_mode=DeviceDisplayMode.FULL)
        ]

        monkeypatch.setenv("HEART_RENDER_CRASH_ON_ERROR", "true")
        monkeypatch.setattr(
            ComposedRenderer,
            "_render_renderer",
            staticmethod(lambda _renderer, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))),
        )

        with pytest.raises(RuntimeError, match="boom"):
            loop.render_frame(renderers)
