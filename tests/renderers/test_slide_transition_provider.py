"""Property-based tests for the slide transition provider."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.slide_transition.provider import SlideTransitionProvider
from heart.renderers.slide_transition.state import SlideTransitionState


class _StubClock:
    def __init__(self, delta_ms: float) -> None:
        self._delta_ms = delta_ms

    def get_time(self) -> float:
        return self._delta_ms


@st.composite
def _advance_inputs(draw: st.DrawFn) -> tuple[float, int, float]:
    fraction_offset = draw(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    slide_duration_ms = draw(st.integers(min_value=1, max_value=5000))
    delta_ms = draw(
        st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    return fraction_offset, slide_duration_ms, delta_ms


class TestSlideTransitionProviderStateTransitions:
    """Property checks for slide transitions so renderer sequencing stays stable under motion."""

    @given(data=_advance_inputs())
    def test_advance_state_moves_toward_target(self, data: tuple[float, int, float]) -> None:
        """Verify slide steps advance toward completion so transitions finish predictably."""
        fraction_offset, slide_duration_ms, delta_ms = data
        state = SlideTransitionState(
            peripheral_manager=PeripheralManager(),
            fraction_offset=fraction_offset,
            sliding=True,
        )

        result = SlideTransitionProvider._advance(
            state=state,
            clock=_StubClock(delta_ms=delta_ms),
            slide_duration_ms=slide_duration_ms,
        )

        expected = min(1.0, fraction_offset + (delta_ms / slide_duration_ms))
        assert math.isclose(result.fraction_offset, expected, rel_tol=0.0, abs_tol=1e-6)
        if expected >= 1.0:
            assert result.sliding is False
        else:
            assert result.sliding is True

    def test_advance_state_keeps_idle_state(self) -> None:
        """Verify idle transitions stay unchanged so halted slides do not jitter."""
        state = SlideTransitionState(
            peripheral_manager=PeripheralManager(),
            fraction_offset=0.25,
            sliding=False,
        )

        result = SlideTransitionProvider._advance(
            state=state,
            clock=_StubClock(delta_ms=16.0),
            slide_duration_ms=1000,
        )

        assert result == state
