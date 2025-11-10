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


class TestNavigationSortedComposedRenderer:
    """Group Navigation Sorted Composed Renderer tests so navigation sorted composed renderer behaviour stays reliable. This preserves confidence in navigation sorted composed renderer for end-to-end scenarios."""

    def test_sorted_composed_renderer_uses_sorter(self, manager) -> None:
        """Verify that SortedComposedRenderer applies the sorter to reorder renderers. This enables dynamic presentation logic so layouts can adjust to context."""
        renderers = [_StubRenderer(label) for label in ["beta", "alpha", "gamma"]]

        composer = SortedComposedRenderer(
            renderers, sorter=lambda rs, _: sorted(rs, key=lambda item: item.label)
        )

        ordered = composer.get_renderers(manager)
        assert [renderer.label for renderer in ordered] == ["alpha", "beta", "gamma"]



    def test_sorted_composed_renderer_rejects_invalid_permutation(self, manager) -> None:
        """Verify that SortedComposedRenderer raises when the sorter drops renderers from the result. This prevents subtle bugs where UI sections disappear due to mis-sorted lists."""
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
    def test_switch_controlled_renderer_order(self, rotation, button, expected) -> None:
        """Verify that switch_controlled_renderer_order rotates renderers based on switch state and button offset. This ties hardware controls to visual ordering for user-driven customization."""
        renderers = tuple(
            _StubRenderer(label) for label in ["gamma", "alpha", "beta"]
        )
        manager = _StubPeripheralManager(
            _StubSwitch(rotation=rotation, button=button)
        )

        ordered = switch_controlled_renderer_order(renderers, manager)

        assert [renderer.label for renderer in ordered] == expected
