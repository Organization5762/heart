import pytest

from heart.display.renderers import BaseRenderer
from heart.navigation import (SortedComposedRenderer,
                              switch_controlled_renderer_order)


class _StubRenderer(BaseRenderer):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    @property
    def name(self) -> str:
        return self.label

    def get_renderers(self, peripheral_manager):  # pragma: no cover - trivial
        return [self]


class _StubSwitch:
    def __init__(self, *, rotation: int = 0, button: int = 0) -> None:
        self._rotation = rotation
        self._button = button

    def get_rotation_since_last_button_press(self) -> int:
        return self._rotation

    def get_button_value(self) -> int:
        return self._button


class _StubPeripheralManager:
    def __init__(self, switch: _StubSwitch) -> None:
        self._switch = switch

    def _deprecated_get_main_switch(self) -> _StubSwitch:
        return self._switch


def test_sorted_composed_renderer_uses_sorter(manager) -> None:
    renderers = [_StubRenderer(label) for label in ["beta", "alpha", "gamma"]]

    composer = SortedComposedRenderer(
        renderers, sorter=lambda rs, _: sorted(rs, key=lambda item: item.label)
    )

    ordered = composer.get_renderers(manager)
    assert [renderer.label for renderer in ordered] == ["alpha", "beta", "gamma"]


def test_sorted_composed_renderer_rejects_invalid_permutation(manager) -> None:
    renderers = [_StubRenderer(label) for label in ["a", "b"]]

    composer = SortedComposedRenderer(
        renderers, sorter=lambda rs, _: rs[:-1]  # drop one renderer
    )

    with pytest.raises(ValueError):
        composer.get_renderers(manager)


@pytest.mark.parametrize(
    "rotation,button,expected",
    [
        (0, 0, ["alpha", "beta", "gamma"]),
        (1, 0, ["beta", "gamma", "alpha"]),
        (2, 1, ["alpha", "gamma", "beta"]),
    ],
)
def test_switch_controlled_renderer_order(rotation, button, expected) -> None:
    renderers = tuple(
        _StubRenderer(label) for label in ["gamma", "alpha", "beta"]
    )
    manager = _StubPeripheralManager(
        _StubSwitch(rotation=rotation, button=button)
    )

    ordered = switch_controlled_renderer_order(renderers, manager)

    assert [renderer.label for renderer in ordered] == expected
