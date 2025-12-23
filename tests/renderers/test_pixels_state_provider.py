"""Property-based tests for pixel renderer state providers."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from hypothesis import given
from hypothesis import strategies as st

from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.pixels.provider import (RainStateProvider,
                                             SlinkyStateProvider)
from heart.renderers.pixels.state import RainState, SlinkyState


@dataclass
class _StubRandom:
    value: int
    fail_on_call: bool = False
    calls: int = 0

    def randint(self, _min: int, _max: int) -> int:
        if self.fail_on_call:
            raise AssertionError("randint should not be called in this transition")
        self.calls += 1
        return self.value


@st.composite
def _advance_state(draw: st.DrawFn) -> tuple[int, int, int, int]:
    width = draw(st.integers(min_value=1, max_value=256))
    height = draw(st.integers(min_value=1, max_value=256))
    starting_point = draw(st.integers(min_value=0, max_value=width))
    current_y = draw(st.integers(min_value=0, max_value=height - 1))
    return width, height, starting_point, current_y


@st.composite
def _reset_state(draw: st.DrawFn) -> tuple[int, int, int, int, int]:
    width = draw(st.integers(min_value=1, max_value=256))
    height = draw(st.integers(min_value=0, max_value=256))
    starting_point = draw(st.integers(min_value=0, max_value=width))
    reset_value = draw(st.integers(min_value=0, max_value=width))
    current_y = draw(st.integers(min_value=height, max_value=height + 32))
    return width, height, starting_point, current_y, reset_value


class TestPixelStateProviderTransitions:
    """Property checks for state provider transitions to preserve animation stability."""

    @pytest.mark.parametrize(
        ("provider_cls", "state_cls"),
        [
            (RainStateProvider, RainState),
            (SlinkyStateProvider, SlinkyState),
        ],
    )
    @given(data=_advance_state())
    def test_next_state_advances_without_reset(
        self,
        provider_cls,
        state_cls,
        data: tuple[int, int, int, int],
    ) -> None:
        """Verify upward steps increment position without reset so steady animations remain smooth."""
        width, height, starting_point, current_y = data
        rng = _StubRandom(value=0, fail_on_call=True)
        provider = provider_cls(
            width=width,
            height=height,
            peripheral_manager=PeripheralManager(),
            rng=rng,
        )
        state = state_cls(starting_point=starting_point, current_y=current_y)

        result = provider._next_state(state)

        assert result.current_y == current_y + 1
        assert result.starting_point == starting_point
        assert rng.calls == 0

    @pytest.mark.parametrize(
        ("provider_cls", "state_cls"),
        [
            (RainStateProvider, RainState),
            (SlinkyStateProvider, SlinkyState),
        ],
    )
    @given(data=_reset_state())
    def test_next_state_resets_after_height(
        self,
        provider_cls,
        state_cls,
        data: tuple[int, int, int, int, int],
    ) -> None:
        """Verify overflow resets to zero so drops loop cleanly for continuous effects."""
        width, height, starting_point, current_y, reset_value = data
        rng = _StubRandom(value=reset_value)
        provider = provider_cls(
            width=width,
            height=height,
            peripheral_manager=PeripheralManager(),
            rng=rng,
        )
        state = state_cls(starting_point=starting_point, current_y=current_y)

        result = provider._next_state(state)

        assert result.current_y == 0
        assert result.starting_point == reset_value
        assert rng.calls == 1
