"""Validate Hilbert renderer sizing against mirrored display tiles."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import reactivex

from heart.renderers.hilbert_curve.provider import (compute_zoom_target_scale,
                                                    hilbert_curve_points_numba)
from heart.renderers.hilbert_curve.renderer import HilbertScene


@dataclass(frozen=True)
class _StubHilbertState:
    width: int
    height: int


class _StubHilbertProvider:
    def __init__(self) -> None:
        self.initial_state_calls: list[tuple[int, int]] = []
        self.observable_initial_states: list[_StubHilbertState] = []

    def initial_state(self, *, width: int, height: int) -> _StubHilbertState:
        self.initial_state_calls.append((width, height))
        return _StubHilbertState(width=width, height=height)

    def observable(self, peripheral_manager, *, initial_state: _StubHilbertState):
        self.observable_initial_states.append(initial_state)
        return reactivex.just(initial_state)


class TestHilbertScene:
    """Ensure the Hilbert scene sizes curves from the actual render tile so mirrored output does not clip or undershoot."""

    def test_point_generation_preserves_square_aspect_ratio(self) -> None:
        """Verify Hilbert point generation uses a uniform step so mirrored Hilbert boxes stay square instead of stretching to match rectangular tiles."""
        points = hilbert_curve_points_numba(
            order=1,
            width=64,
            height=96,
            xmargin=0,
            ymargin=0,
        )

        assert np.isclose(points[:, 0].min(), 0.0)
        assert np.isclose(points[:, 0].max(), 64.0)
        assert np.isclose(points[:, 1].min(), 0.0)
        assert np.isclose(points[:, 1].max(), 64.0)

    def test_initialize_uses_actual_window_size(
        self,
        manager,
    ) -> None:
        """Verify initialization seeds the provider from the actual window size so mirrored Hilbert curves fit the scratch tile instead of the full display."""
        provider = _StubHilbertProvider()
        scene = HilbertScene(provider=provider)
        window = type("Window", (), {"get_size": lambda self: (64, 64)})()
        orientation = object()

        scene.initialize(window, manager, orientation)

        assert provider.initial_state_calls == [(64, 64)]
        assert provider.observable_initial_states == [_StubHilbertState(64, 64)]

    def test_zoom_target_scale_fits_zoom_bbox_to_available_rect(self) -> None:
        """Verify zoom target scale is derived from the available render rect so Hilbert zoom fills the intended height without relying on a magic multiplier."""
        scale = compute_zoom_target_scale(
            width=1024,
            height=256,
            xmargin=0,
            ymargin=0,
            bbox=(0.0, 0.0, 5.876694756088149, 2.015748031496063),
        )

        assert np.isclose(scale, 256 / 2.015748031496063)
