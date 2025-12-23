"""Property-based tests for heart title screen provider transitions."""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.heart_title_screen.provider import (
    DEFAULT_TIME_BETWEEN_FRAMES_MS, HeartTitleScreenStateProvider)
from heart.renderers.heart_title_screen.state import HeartTitleScreenState


@st.composite
def _timing_inputs(draw: st.DrawFn) -> tuple[float, float, bool]:
    elapsed_ms = draw(
        st.floats(min_value=0, max_value=2000, allow_nan=False, allow_infinity=False)
    )
    frame_ms = draw(
        st.floats(
            min_value=-500,
            max_value=2000,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    heart_up = draw(st.booleans())
    return elapsed_ms, frame_ms, heart_up


class TestHeartTitleScreenProviderTransitions:
    """Group heart title provider checks so animation toggles remain deterministic."""

    @given(data=_timing_inputs())
    def test_advance_state_accumulates_below_threshold(
        self, data: tuple[float, float, bool]
    ) -> None:
        """Verify elapsed time accumulates below the threshold so title pulses stay steady."""
        elapsed_ms, frame_ms, heart_up = data
        provider = HeartTitleScreenStateProvider(PeripheralManager())
        state = HeartTitleScreenState(heart_up=heart_up, elapsed_ms=elapsed_ms)
        safe_frame_ms = max(frame_ms, 0.0)
        total = elapsed_ms + safe_frame_ms
        assume(total <= DEFAULT_TIME_BETWEEN_FRAMES_MS)

        result = provider._advance_state(state=state, frame_ms=frame_ms)

        assert result.heart_up is heart_up
        assert result.elapsed_ms == total

    @given(data=_timing_inputs())
    def test_advance_state_toggles_above_threshold(
        self, data: tuple[float, float, bool]
    ) -> None:
        """Verify exceeding the threshold flips heart frames so animations keep pulsing."""
        elapsed_ms, frame_ms, heart_up = data
        provider = HeartTitleScreenStateProvider(PeripheralManager())
        state = HeartTitleScreenState(heart_up=heart_up, elapsed_ms=elapsed_ms)
        safe_frame_ms = max(frame_ms, 0.0)
        total = elapsed_ms + safe_frame_ms
        assume(total > DEFAULT_TIME_BETWEEN_FRAMES_MS)

        result = provider._advance_state(state=state, frame_ms=frame_ms)

        assert result.heart_up is not heart_up
        assert result.elapsed_ms == 0.0
