"""Property-based tests for metadata screen state providers."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from heart.renderers.metadata_screen import provider as provider_module
from heart.renderers.metadata_screen.provider import (
    DEFAULT_TIME_BETWEEN_FRAMES_MS, MetadataScreenStateProvider)
from heart.renderers.metadata_screen.state import (DEFAULT_HEART_COLORS,
                                                   HeartAnimationState,
                                                   MetadataScreenState)


@st.composite
def _monitor_sets(
    draw: st.DrawFn,
) -> tuple[list[str], list[str], list[str]]:
    alphabet = st.characters(min_codepoint=97, max_codepoint=122)
    active_monitors = draw(
        st.lists(
            st.text(alphabet=alphabet, min_size=1, max_size=4),
            min_size=1,
            max_size=6,
            unique=True,
        )
    )
    extra_monitors = draw(
        st.lists(
            st.text(alphabet=alphabet, min_size=1, max_size=4),
            min_size=0,
            max_size=4,
            unique=True,
        ).filter(lambda items: set(items).isdisjoint(active_monitors))
    )
    combined = active_monitors + extra_monitors
    existing_monitors = draw(
        st.lists(
            st.sampled_from(combined),
            min_size=0,
            max_size=len(combined),
            unique=True,
        )
    )
    return active_monitors, extra_monitors, existing_monitors


@st.composite
def _animation_inputs(
    draw: st.DrawFn,
) -> tuple[int, float, float, bool, int]:
    bpm = draw(st.integers(min_value=0, max_value=240))
    elapsed_ms = draw(
        st.floats(
            min_value=0,
            max_value=2000,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    last_update_ms = draw(
        st.floats(
            min_value=0,
            max_value=2000,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    up = draw(st.booleans())
    color_index = draw(
        st.integers(min_value=0, max_value=len(DEFAULT_HEART_COLORS) - 1)
    )
    return bpm, elapsed_ms, last_update_ms, up, color_index


class TestMetadataScreenProviderTransitions:
    """Group metadata screen provider checks so animation state changes stay stable."""

    @given(data=_monitor_sets())
    def test_update_state_tracks_active_monitors(
        self,
        data: tuple[list[str], list[str], list[str]],
    ) -> None:
        """Verify active monitors drive heart state membership so the UI reflects live devices."""
        active_monitors, _, existing_monitors = data
        colors = ["red", "green", "blue"]
        provider = MetadataScreenStateProvider(colors=colors)
        heart_states = {
            monitor_id: HeartAnimationState(
                up=False,
                color_index=1,
                last_update_ms=0.0,
            )
            for monitor_id in existing_monitors
        }
        state = MetadataScreenState(
            heart_states=heart_states,
            time_since_last_update_ms=12.0,
        )
        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(
                provider_module,
                "current_bpms",
                {monitor_id: 0 for monitor_id in active_monitors},
            )

            result = provider._update_state(
                state=state,
                active_monitors=active_monitors,
                elapsed_ms=0.0,
            )
        finally:
            monkeypatch.undo()

        assert set(result.heart_states.keys()) == set(active_monitors)
        assert result.time_since_last_update_ms == state.time_since_last_update_ms
        for monitor_id in active_monitors:
            animation = result.heart_states[monitor_id]
            if monitor_id in heart_states:
                assert animation == heart_states[monitor_id]
            else:
                expected_index = active_monitors.index(monitor_id) % len(colors)
                assert animation.color_index == expected_index
                assert animation.up is True
                assert animation.last_update_ms == 0.0

    @given(data=_animation_inputs())
    def test_update_state_advances_animation_frames(
        self,
        data: tuple[int, float, float, bool, int],
    ) -> None:
        """Verify elapsed time toggles heart frames so the visual pulse matches BPM timing."""
        bpm, elapsed_ms, last_update_ms, up, color_index = data
        provider = MetadataScreenStateProvider()
        monitor_id = "pulse-1"
        state = MetadataScreenState(
            heart_states={
                monitor_id: HeartAnimationState(
                    up=up,
                    color_index=color_index,
                    last_update_ms=last_update_ms,
                )
            },
            time_since_last_update_ms=5.0,
        )
        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(provider_module, "current_bpms", {monitor_id: bpm})

            result = provider._update_state(
                state=state,
                active_monitors=[monitor_id],
                elapsed_ms=elapsed_ms,
            )
        finally:
            monkeypatch.undo()

        time_between_beats = (
            60000 / bpm / 2 if bpm > 0 else DEFAULT_TIME_BETWEEN_FRAMES_MS
        )
        accumulated = last_update_ms + elapsed_ms
        if accumulated > time_between_beats:
            expected_up = not up
            expected_last_update = 0.0
        else:
            expected_up = up
            expected_last_update = accumulated

        animation = result.heart_states[monitor_id]
        assert animation.up == expected_up
        assert animation.color_index == color_index
        assert math.isclose(animation.last_update_ms, expected_last_update)
        assert math.isclose(
            result.time_since_last_update_ms,
            state.time_since_last_update_ms + elapsed_ms,
        )
