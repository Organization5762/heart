from __future__ import annotations

from heart.display.color import Color
from heart.renderers.pixels.provider import BorderStateProvider
from heart.renderers.pixels.state import BorderState


def test_border_provider_uses_value_for_current_color() -> None:
    initial = Color(r=1, g=2, b=3)
    updated = Color(r=4, g=5, b=6)
    provider = BorderStateProvider(initial)
    observed: list[BorderState] = []

    provider.observable().subscribe(observed.append)
    provider.set_color(updated)

    assert observed == [BorderState(color=initial), BorderState(color=updated)]
