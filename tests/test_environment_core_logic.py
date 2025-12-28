"""Additional tests for runtime and color conversion helpers."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from heart.runtime.render.pipeline import RendererVariant
from heart.utilities.color_conversion import (HSV_TO_BGR_CACHE,
                                              _convert_bgr_to_hsv,
                                              _convert_hsv_to_bgr)
from heart.utilities.env import Configuration


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



    @pytest.mark.parametrize("values", [list("abcd"), list("abcde")])
    def test_render_surfaces_binary_merges_all(
        self,
        loop, monkeypatch, render_merge_strategy_in_place, values: list[str]
    ) -> None:
        """Verify that the render pipeline binary merge combines all renderers. This validates the pairwise merge optimisation for high-FPS scenes."""
        renderers = [SimpleNamespace(name=value) for value in values]
        sequence = {renderer.name: f"surface-{renderer.name}" for renderer in renderers}
        pipeline = loop.render_pipeline

        def fake_process(renderer: SimpleNamespace) -> str:
            return sequence[renderer.name]

        def fake_merge(surface1: str, surface2: str) -> str:
            return f"merge({surface1},{surface2})"

        monkeypatch.setattr(pipeline, "process_renderer", fake_process)
        monkeypatch.setattr(pipeline, "merge_surfaces", fake_merge)

        result = pipeline._render_surfaces_binary(renderers)
        expected = _sequential_binary_merge(list(sequence.values()))
        assert result == expected



    def test_render_surfaces_binary_handles_empty(self, loop) -> None:
        """Verify that the render pipeline returns None with no renderers. This avoids edge-case crashes during startup."""
        assert loop.render_pipeline._render_surfaces_binary([]) is None



    def test_render_surface_iterative_skips_missing(
        self, loop, monkeypatch, render_merge_strategy_in_place
    ) -> None:
        """Verify that the render pipeline skips missing surfaces while merging. This ensures null-producing renderers do not break composition."""
        renderers = [SimpleNamespace(name=renderer) for renderer in ["r1", "r2", "r3"]]
        responses = {"r1": "surface-1", "r2": None, "r3": "surface-3"}
        merges: list[tuple[str, str]] = []
        pipeline = loop.render_pipeline

        def fake_process(renderer: SimpleNamespace) -> str | None:
            return responses[renderer.name]

        def fake_merge(surface1: str, surface2: str) -> str:
            merges.append((surface1, surface2))
            return f"merge({surface1},{surface2})"

        monkeypatch.setattr(pipeline, "process_renderer", fake_process)
        monkeypatch.setattr(pipeline, "merge_surfaces", fake_merge)

        result = pipeline._render_surface_iterative(renderers)

        assert result == "merge(surface-1,surface-3)"
        assert merges == [("surface-1", "surface-3")]


    def test_render_fn_selects_renderer(self, loop) -> None:
        """Verify that the render pipeline selects the expected merge strategy. This keeps render mode selection predictable."""
        renderers = [SimpleNamespace(name="r1"), SimpleNamespace(name="r2")]
        pipeline = loop.render_pipeline
        assert (
            pipeline._render_fn(renderers, RendererVariant.BINARY)
            is pipeline._render_surfaces_binary
        )
        assert (
            pipeline._render_fn(renderers, RendererVariant.ITERATIVE)
            is pipeline._render_surface_iterative
        )


    def test_render_fn_default_uses_loop_variant(self, loop) -> None:
        """Verify that the render pipeline respects its configured renderer variant. This keeps runtime switches effective without reconfiguring callers."""
        renderers = [SimpleNamespace(name="r1")]
        pipeline = loop.render_pipeline
        pipeline.renderer_variant = RendererVariant.BINARY
        assert pipeline._render_fn(renderers, None) is pipeline._render_surfaces_binary
        pipeline.renderer_variant = RendererVariant.ITERATIVE
        assert (
            pipeline._render_fn(renderers, None) is pipeline._render_surface_iterative
        )


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



    @pytest.mark.parametrize(
        "variant",
        list(RendererVariant),
    )
    def test_render_fn_handles_unknown_variant(self, loop, variant: RendererVariant) -> None:
        """Verify that the render pipeline returns a callable for each variant. This avoids runtime errors when iterating through supported strategies."""
        renderers = [
            SimpleNamespace(name="r1"),
            SimpleNamespace(name="r2"),
            SimpleNamespace(name="r3"),
            SimpleNamespace(name="r4"),
        ]
        assert callable(loop.render_pipeline._render_fn(renderers, variant))


    def test_render_fn_auto_uses_threshold(self, loop, monkeypatch) -> None:
        """Verify that auto rendering switches at the threshold in the pipeline. This keeps performance tuning predictable on constrained devices."""
        monkeypatch.setattr(
            "heart.runtime.render.pipeline.Configuration.render_parallel_threshold",
            lambda: 2,
        )
        monkeypatch.setattr(
            "heart.runtime.render.pipeline.Configuration.render_parallel_cost_threshold_ms",
            lambda: 0,
        )
        pipeline = loop.render_pipeline

        assert (
            pipeline._render_fn([SimpleNamespace(name="r1")], RendererVariant.AUTO)
            is pipeline._render_surface_iterative
        )
        assert (
            pipeline._render_fn(
                [SimpleNamespace(name="r1"), SimpleNamespace(name="r2")],
                RendererVariant.AUTO,
            )
            is pipeline._render_surfaces_binary
        )

    def test_render_fn_auto_uses_cost_estimates(self, loop, monkeypatch) -> None:
        """Verify auto rendering uses timing estimates to choose parallelism. This keeps scheduling overhead aligned with actual renderer costs."""
        monkeypatch.setattr(
            "heart.runtime.render.pipeline.Configuration.render_parallel_threshold",
            lambda: 2,
        )
        monkeypatch.setattr(
            "heart.runtime.render.pipeline.Configuration.render_parallel_cost_threshold_ms",
            lambda: 5,
        )
        pipeline = loop.render_pipeline
        renderers = [SimpleNamespace(name="r1"), SimpleNamespace(name="r2")]
        pipeline._timing_tracker.record("r1", 4.0)
        pipeline._timing_tracker.record("r2", 3.0)

        assert (
            pipeline._render_fn(renderers, RendererVariant.AUTO)
            is pipeline._render_surfaces_binary
        )

    @pytest.mark.skip(reason="Flame renderer is not implemented")
    def test_ensure_flame_renderer_returns_singleton_with_marker(self, loop) -> None:
        """Verify that _ensure_flame_renderer caches a marked flame renderer instance. This keeps flame overlays stable and avoids churn in render queues."""

        first = loop._ensure_flame_renderer()
        second = loop._ensure_flame_renderer()

        assert first is second
        assert getattr(first, "is_flame_renderer") is True


def _sequential_binary_merge(values: list[str]) -> str:
    surfaces = list(values)
    while len(surfaces) > 1:
        pairs = [(surfaces[i], surfaces[i + 1]) for i in range(0, len(surfaces) - 1, 2)]
        merged_surfaces = [f"merge({a},{b})" for a, b in pairs]
        if len(surfaces) % 2 == 1:
            merged_surfaces.append(surfaces[-1])
        surfaces = merged_surfaces
    return surfaces[0]
