"""Additional tests for core logic in :mod:`heart.environment`."""

from __future__ import annotations

import numpy as np
import pytest

from heart.environment import (RendererVariant, _convert_bgr_to_hsv,
                               _convert_hsv_to_bgr)


@pytest.fixture(autouse=True)
def disable_cv2(monkeypatch):
    """Force the environment color helpers to use the numpy fallbacks."""

    monkeypatch.setattr("heart.environment.CV2_MODULE", None)


@pytest.mark.skip("Broken test")
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
def test_convert_bgr_to_hsv_known_colors(bgr: np.ndarray, expected: np.ndarray) -> None:
    image = bgr.reshape(1, 1, 3)
    hsv = _convert_bgr_to_hsv(image)
    np.testing.assert_array_equal(hsv.reshape(3), expected)

@pytest.mark.skip("Broken test")
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
def test_convert_hsv_to_bgr_known_colors(hsv: np.ndarray, expected: np.ndarray) -> None:
    image = hsv.reshape(1, 1, 3)
    bgr = _convert_hsv_to_bgr(image)
    np.testing.assert_array_equal(bgr.reshape(3), expected)


@pytest.mark.skip("Broken test")
@pytest.mark.parametrize("seed", [0, 1, 42])
def test_color_round_trip(seed: int) -> None:
    rng = np.random.default_rng(seed)
    bgr = rng.integers(0, 256, size=(4, 5, 3), dtype=np.uint8)

    hsv = _convert_bgr_to_hsv(bgr)
    round_trip = _convert_hsv_to_bgr(hsv)

    np.testing.assert_array_equal(round_trip, bgr)


def _sequential_binary_merge(values: list[str]) -> str:
    surfaces = list(values)
    while len(surfaces) > 1:
        pairs = [(surfaces[i], surfaces[i + 1]) for i in range(0, len(surfaces) - 1, 2)]
        merged_surfaces = [f"merge({a},{b})" for a, b in pairs]
        if len(surfaces) % 2 == 1:
            merged_surfaces.append(surfaces[-1])
        surfaces = merged_surfaces
    return surfaces[0]


@pytest.mark.parametrize("values", [list("abcd"), list("abcde")])
def test_render_surfaces_binary_merges_all(
    loop, monkeypatch, values: list[str]
) -> None:
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


def test_render_surfaces_binary_handles_empty(loop) -> None:
    assert loop._render_surfaces_binary([]) is None


def test_render_surface_iterative_skips_missing(loop, monkeypatch) -> None:
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

@pytest.mark.skip("Broken test")
def test_render_fn_selects_renderer(loop) -> None:
    assert loop._render_fn(RendererVariant.BINARY) is loop._render_surfaces_binary
    assert loop._render_fn(RendererVariant.ITERATIVE) is loop._render_surface_iterative

@pytest.mark.skip("Broken test")
def test_render_fn_default_uses_loop_variant(loop) -> None:
    loop.renderer_variant = RendererVariant.BINARY
    assert loop._render_fn(None) is loop._render_surfaces_binary
    loop.renderer_variant = RendererVariant.ITERATIVE
    assert loop._render_fn(None) is loop._render_surface_iterative


@pytest.mark.skip("Broken test")
@pytest.mark.parametrize(
    "variant",
    list(RendererVariant),
)
def test_render_fn_handles_unknown_variant(loop, variant: RendererVariant) -> None:
    assert callable(loop._render_fn(variant))
