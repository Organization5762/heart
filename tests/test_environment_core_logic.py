"""Additional tests for core logic in :mod:`heart.environment`."""

from __future__ import annotations

import types

import numpy as np
import pytest

from heart.display.renderers.free_text import FreeTextRenderer
from heart.environment import (HSV_TO_BGR_CACHE, RendererVariant,
                               _convert_bgr_to_hsv, _convert_hsv_to_bgr)
from heart.events.types import PhoneTextMessage


@pytest.fixture(autouse=True)
def disable_cv2(monkeypatch):
    """Force the environment color helpers to use the numpy fallbacks."""

    monkeypatch.setattr("heart.environment.CV2_MODULE", None)


@pytest.fixture(autouse=True)
def clear_hsv_cache():
    """Ensure colour conversion cache state is isolated between tests."""

    HSV_TO_BGR_CACHE.clear()
    yield
    HSV_TO_BGR_CACHE.clear()


class TestEnvironmentCoreLogic:
    """Group Environment Core Logic tests so environment core logic behaviour stays reliable. This preserves confidence in environment core logic for end-to-end scenarios."""

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
        loop, monkeypatch, values: list[str]
    ) -> None:
        """Verify that _render_surfaces_binary merges all renderers pairwise. This validates the binary merge optimisation powering high-FPS scenes."""
        sequence = {value: f"surface-{value}" for value in values}

        def fake_process(renderer: str) -> str:
            return sequence[renderer]

        def fake_merge(surface1: str, surface2: str) -> str:
            return f"merge({surface1},{surface2})"

        monkeypatch.setattr(loop, "process_renderer", fake_process)
        monkeypatch.setattr(loop, "merge_surfaces", fake_merge)

        result = loop._render_surfaces_binary(values)
        expected = _sequential_binary_merge(list(sequence.values()))
        assert result == expected



    def test_render_surfaces_binary_handles_empty(self, loop) -> None:
        """Verify that _render_surfaces_binary returns None when no renderers are provided. This avoids edge-case crashes during startup."""
        assert loop._render_surfaces_binary([]) is None



    def test_render_surface_iterative_skips_missing(self, loop, monkeypatch) -> None:
        """Verify that _render_surface_iterative skips missing surfaces while merging. This ensures null-producing renderers do not break composition."""
        renderers = ["r1", "r2", "r3"]
        responses = {"r1": "surface-1", "r2": None, "r3": "surface-3"}
        merges: list[tuple[str, str]] = []

        def fake_process(renderer: str) -> str | None:
            return responses[renderer]

        def fake_merge(surface1: str, surface2: str) -> str:
            merges.append((surface1, surface2))
            return f"merge({surface1},{surface2})"

        monkeypatch.setattr(loop, "process_renderer", fake_process)
        monkeypatch.setattr(loop, "merge_surfaces", fake_merge)

        result = loop._render_surface_iterative(renderers)

        assert result == "merge(surface-1,surface-3)"
        assert merges == [("surface-1", "surface-3")]


    def test_render_fn_selects_renderer(self, loop) -> None:
        """Verify that _render_fn returns the expected merge strategy for each variant. This keeps render mode selection predictable."""
        assert loop._render_fn(RendererVariant.BINARY) is loop._render_surfaces_binary
        assert loop._render_fn(RendererVariant.ITERATIVE) is loop._render_surface_iterative


    def test_render_fn_default_uses_loop_variant(self, loop) -> None:
        """Verify that _render_fn respects the loop's configured renderer variant by default. This keeps runtime switches effective without reconfiguring callers."""
        loop.renderer_variant = RendererVariant.BINARY
        assert loop._render_fn(None) is loop._render_surfaces_binary
        loop.renderer_variant = RendererVariant.ITERATIVE
        assert loop._render_fn(None) is loop._render_surface_iterative



    @pytest.mark.parametrize(
        "variant",
        list(RendererVariant),
    )
    def test_render_fn_handles_unknown_variant(self, loop, variant: RendererVariant) -> None:
        """Verify that _render_fn returns a callable even for enumerated variants. This avoids runtime errors when iterating through supported strategies."""
        assert callable(loop._render_fn(variant))



    def test_phone_text_event_triggers_transient_renderer(self, loop, monkeypatch) -> None:
        """Verify that a phone text event spawns a transient renderer and expires after the timeout. This ensures pop-up messages show briefly without blocking other scenes."""
        current_time = 1000.0

        monkeypatch.setattr("heart.environment.time.monotonic", lambda: current_time)
        loop.app_controller = types.SimpleNamespace(
            get_renderers=lambda *args, **kwargs: [],
        )

        assert loop._select_renderers() == []

        loop.event_bus.emit(
            PhoneTextMessage.EVENT_TYPE,
            {"text": "Heart: hello"},
        )

        active_renderers = loop._select_renderers()
        assert len(active_renderers) == 1
        renderer = active_renderers[0]
        assert isinstance(renderer, FreeTextRenderer)

        current_time += loop._phone_text_duration - 1.0
        assert loop._select_renderers() == [renderer]

        current_time += 2.0
        assert loop._select_renderers() == []
        assert loop._phone_text_display_started_at is None

def _sequential_binary_merge(values: list[str]) -> str:
    surfaces = list(values)
    while len(surfaces) > 1:
        pairs = [(surfaces[i], surfaces[i + 1]) for i in range(0, len(surfaces) - 1, 2)]
        merged_surfaces = [f"merge({a},{b})" for a, b in pairs]
        if len(surfaces) % 2 == 1:
            merged_surfaces.append(surfaces[-1])
        surfaces = merged_surfaces
    return surfaces[0]
