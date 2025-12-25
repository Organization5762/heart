"""Property-based tests for the slide transition provider."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.slide_transition.provider import SlideTransitionProvider
from heart.renderers.slide_transition.state import SlideTransitionState


@st.composite
def _advance_inputs(draw: st.DrawFn) -> tuple[int, int, int, int]:
    direction = draw(st.sampled_from([-1, 1]))
    slide_speed = draw(st.integers(min_value=1, max_value=64))
    screen_width = draw(st.integers(min_value=1, max_value=256))
    target_offset = -direction * screen_width
    x_offset = draw(
        st.integers(min_value=target_offset - 256, max_value=target_offset + 256)
    )
    return direction, slide_speed, screen_width, x_offset


@st.composite
def _steady_inputs(draw: st.DrawFn) -> tuple[int, int, int, int]:
    direction = draw(st.sampled_from([-1, 1]))
    slide_speed = draw(st.integers(min_value=1, max_value=64))
    screen_width = draw(st.integers(min_value=1, max_value=256))
    x_offset = draw(st.integers(min_value=-512, max_value=512))
    return direction, slide_speed, screen_width, x_offset


@st.composite
def _screen_refresh_inputs(draw: st.DrawFn) -> tuple[int, int, int]:
    direction = draw(st.sampled_from([-1, 1]))
    slide_speed = draw(st.integers(min_value=1, max_value=64))
    screen_width = draw(st.integers(min_value=1, max_value=256))
    return direction, slide_speed, screen_width


class TestSlideTransitionProviderStateTransitions:
    """Property checks for slide transitions so renderer sequencing stays stable under motion."""

    class _StubRenderer(StatefulBaseRenderer[int]):
        def _create_initial_state(self, window, clock, peripheral_manager, orientation) -> int:
            return 0

        def real_process(self, window, clock, orientation) -> None:
            pass

    @given(data=_advance_inputs())
    def test_update_state_moves_toward_target(self, data: tuple[int, int, int, int]) -> None:
        """Verify slide steps advance toward the target offset so scenes converge deterministically."""
        direction, slide_speed, screen_width, x_offset = data
        target_offset = -direction * screen_width
        provider = SlideTransitionProvider(
            self._StubRenderer(),
            self._StubRenderer(),
            direction=direction,
            slide_speed=slide_speed,
        )
        state = SlideTransitionState(
            peripheral_manager=PeripheralManager(),
            x_offset=x_offset,
            target_offset=target_offset,
            sliding=True,
            screen_w=screen_width,
        )

        result = provider.update_state(state=state, screen_width=screen_width)

        assert abs(result.x_offset - target_offset) <= abs(x_offset - target_offset)
        assert result.target_offset == target_offset
        assert result.screen_w == screen_width
        if result.x_offset == target_offset:
            assert result.sliding is False
        else:
            assert abs(result.x_offset - x_offset) <= slide_speed
            assert result.sliding is True

    @given(data=_steady_inputs())
    def test_update_state_keeps_idle_state(self, data: tuple[int, int, int, int]) -> None:
        """Verify idle transitions stay unchanged so halted slides do not jitter."""
        direction, slide_speed, screen_width, x_offset = data
        provider = SlideTransitionProvider(
            self._StubRenderer(),
            self._StubRenderer(),
            direction=direction,
            slide_speed=slide_speed,
        )
        state = SlideTransitionState(
            peripheral_manager=PeripheralManager(),
            x_offset=x_offset,
            target_offset=-direction * screen_width,
            sliding=False,
            screen_w=screen_width,
        )

        result = provider.update_state(state=state, screen_width=screen_width)

        assert result == state

    @given(data=_screen_refresh_inputs())
    def test_update_state_refreshes_missing_target(self, data: tuple[int, int, int]) -> None:
        """Verify missing targets refresh to screen width so transitions restart coherently."""
        direction, slide_speed, screen_width = data
        provider = SlideTransitionProvider(
            self._StubRenderer(),
            self._StubRenderer(),
            direction=direction,
            slide_speed=slide_speed,
        )
        state = SlideTransitionState(
            peripheral_manager=PeripheralManager(),
            x_offset=0,
            target_offset=None,
            sliding=False,
            screen_w=screen_width,
        )

        result = provider.update_state(state=state, screen_width=screen_width)

        assert result.target_offset == -direction * screen_width
        assert result.screen_w == screen_width
        assert result.x_offset == 0
        assert result.sliding is False
