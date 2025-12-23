import numpy as np
import pytest

from heart.modules.life.state import LifeState


class TestLifeUpdateStrategies:
    """Cover Life update strategies to preserve performance and correctness guarantees."""

    @pytest.mark.parametrize(
        "strategy",
        ["auto", "pad"],
        ids=["auto-uses-padding", "pad-uses-padding"],
    )
    def test_padding_strategy_matches_convolution(
        self,
        monkeypatch: pytest.MonkeyPatch,
        strategy: str,
    ) -> None:
        """Confirm padding-based updates match convolution so performance gains do not alter rules."""

        grid = np.array(
            [
                [0, 1, 0, 0, 1],
                [1, 1, 0, 1, 0],
                [0, 0, 1, 0, 0],
                [1, 0, 0, 1, 1],
                [0, 1, 0, 0, 0],
            ],
            dtype=int,
        )

        monkeypatch.setenv("HEART_LIFE_UPDATE_STRATEGY", "convolve")
        expected = LifeState(grid=grid)._update_grid().grid

        monkeypatch.setenv("HEART_LIFE_UPDATE_STRATEGY", strategy)
        result = LifeState(grid=grid)._update_grid().grid

        assert np.array_equal(
            expected,
            result,
        ), "Padding strategy should preserve the Life update rules."

    def test_padding_strategy_rejects_custom_kernel(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure unsupported custom kernels are blocked to avoid incorrect fast paths."""

        grid = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=int)
        kernel = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=int)

        monkeypatch.setenv("HEART_LIFE_UPDATE_STRATEGY", "pad")

        with pytest.raises(ValueError, match="default kernel"):
            LifeState(grid=grid, kernel=kernel)._update_grid()
