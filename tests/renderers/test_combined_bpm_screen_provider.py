"""Property-based tests for the combined BPM screen provider."""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from heart.renderers.combined_bpm_screen.provider import \
    CombinedBpmScreenStateProvider
from heart.renderers.combined_bpm_screen.state import CombinedBpmScreenState


@st.composite
def _timing_inputs(draw: st.DrawFn) -> tuple[int, int, int, int, bool]:
    metadata_duration = draw(st.integers(min_value=1, max_value=20000))
    max_bpm_duration = draw(st.integers(min_value=1, max_value=20000))
    elapsed_time = draw(st.integers(min_value=0, max_value=20000))
    delta = draw(st.integers(min_value=0, max_value=20000))
    showing_metadata = draw(st.booleans())
    return metadata_duration, max_bpm_duration, elapsed_time, delta, showing_metadata


class TestCombinedBpmScreenProviderTransitions:
    """Property tests for combined BPM transitions to keep screen toggles reliable."""

    @given(data=_timing_inputs())
    def test_advance_state_holds_until_threshold(
        self, data: tuple[int, int, int, int, bool]
    ) -> None:
        """Verify elapsed time accumulates when below thresholds so screen phases stay steady."""
        metadata_duration, max_bpm_duration, elapsed_time, delta, showing_metadata = data
        provider = CombinedBpmScreenStateProvider(
            metadata_duration_ms=metadata_duration,
            max_bpm_duration_ms=max_bpm_duration,
        )
        total = elapsed_time + delta
        threshold = metadata_duration if showing_metadata else max_bpm_duration
        assume(total < threshold)
        state = CombinedBpmScreenState(
            elapsed_time_ms=elapsed_time, showing_metadata=showing_metadata
        )

        result = provider._advance_state(state=state, elapsed_ms=delta)

        assert result.elapsed_time_ms == total
        assert result.showing_metadata == showing_metadata

    @given(data=_timing_inputs())
    def test_advance_state_flips_on_threshold(
        self, data: tuple[int, int, int, int, bool]
    ) -> None:
        """Verify exceeding thresholds flips screen phases so render cycles stay predictable."""
        metadata_duration, max_bpm_duration, elapsed_time, delta, showing_metadata = data
        provider = CombinedBpmScreenStateProvider(
            metadata_duration_ms=metadata_duration,
            max_bpm_duration_ms=max_bpm_duration,
        )
        total = elapsed_time + delta
        threshold = metadata_duration if showing_metadata else max_bpm_duration
        assume(total >= threshold)
        state = CombinedBpmScreenState(
            elapsed_time_ms=elapsed_time, showing_metadata=showing_metadata
        )

        result = provider._advance_state(state=state, elapsed_ms=delta)

        assert result.elapsed_time_ms == 0
        assert result.showing_metadata is not showing_metadata
