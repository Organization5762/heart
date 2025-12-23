"""Property-based tests for sliding renderer state providers."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from hypothesis import given
from hypothesis import strategies as st

from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.sliding_image.provider import (
    SlidingImageStateProvider, SlidingRendererStateProvider)
from heart.renderers.sliding_image.state import (SlidingImageState,
                                                 SlidingRendererState)


@dataclass(frozen=True)
class _ProviderSpec:
    provider_cls: type[SlidingImageStateProvider | SlidingRendererStateProvider]
    state_cls: type[SlidingImageState | SlidingRendererState]

    def build_state(self, *, offset: int, speed: int, width: int):
        if self.state_cls is SlidingImageState:
            return self.state_cls(offset=offset, speed=speed, width=width, image=None)
        return self.state_cls(offset=offset, speed=speed, width=width)


PROVIDER_SPECS = [
    _ProviderSpec(SlidingImageStateProvider, SlidingImageState),
    _ProviderSpec(SlidingRendererStateProvider, SlidingRendererState),
]


@st.composite
def _advance_inputs(draw: st.DrawFn) -> tuple[int, int, int]:
    offset = draw(st.integers(min_value=-512, max_value=512))
    speed = draw(st.integers(min_value=1, max_value=32))
    width = draw(st.integers(min_value=-10, max_value=256))
    return offset, speed, width


@st.composite
def _width_inputs(draw: st.DrawFn) -> tuple[int, int, int, int]:
    offset = draw(st.integers(min_value=-512, max_value=512))
    speed = draw(st.integers(min_value=1, max_value=32))
    state_width = draw(st.integers(min_value=-10, max_value=256))
    provider_width = draw(st.integers(min_value=-10, max_value=256))
    return offset, speed, state_width, provider_width


class TestSlidingStateProviderTransitions:
    """Property checks for sliding provider transitions to preserve wraparound consistency."""

    @pytest.mark.parametrize("spec", PROVIDER_SPECS)
    @given(data=_width_inputs())
    def test_advance_state_uses_expected_width(self, spec: _ProviderSpec, data) -> None:
        """Verify width selection follows state or provider so scrolling remains predictable."""
        offset, speed, state_width, provider_width = data
        provider = spec.provider_cls(
            peripheral_manager=PeripheralManager(),
            speed=speed,
            width=provider_width,
        )
        state = spec.build_state(offset=offset, speed=speed, width=state_width)
        expected_width = state_width if state_width != 0 else provider_width

        result = provider.advance_state(state)

        assert result.width == expected_width
        assert result.speed == speed
        if expected_width <= 0:
            assert result.offset == offset
        else:
            assert result.offset == (offset + speed) % expected_width

    @pytest.mark.parametrize("spec", PROVIDER_SPECS)
    @given(data=_advance_inputs())
    def test_reset_state_clears_offset(self, spec: _ProviderSpec, data) -> None:
        """Verify resets zero the offset so replays start at the leading edge reliably."""
        offset, speed, width = data
        provider = spec.provider_cls(
            peripheral_manager=PeripheralManager(),
            speed=speed,
            width=width,
        )
        state = spec.build_state(offset=offset, speed=speed, width=width)

        result = provider.reset_state(state)

        assert result.offset == 0
        assert result.speed == speed
        assert result.width == width
        if isinstance(result, SlidingImageState):
            assert result.image is None
