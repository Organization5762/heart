import numpy as np
import pytest

from heart.renderers.life.state import LifeState


class TestLifeUpdateStrategies:
    """Cover Life update strategies to preserve performance and correctness guarantees."""

    @pytest.mark.parametrize(
        "strategy",
        ["auto", "pad", "shifted"],
        ids=["auto-uses-shifted", "pad-uses-padding", "shifted-uses-slices"],
    )
    def test_fast_strategies_match_convolution(
        self,
        monkeypatch: pytest.MonkeyPatch,
        strategy: str,
    ) -> None:
        """Confirm fast updates match convolution so performance gains do not alter rules."""

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
        monkeypatch.setenv("HEART_LIFE_CONVOLVE_THRESHOLD", "0")
        result = LifeState(grid=grid)._update_grid().grid

        assert np.array_equal(
            expected,
            result,
        ), "Fast strategies should preserve the Life update rules."

    @pytest.mark.parametrize(
        "strategy",
        ["pad", "shifted"],
        ids=["pad-rejects-kernel", "shifted-rejects-kernel"],
    )
    def test_fast_strategy_rejects_custom_kernel(
        self,
        monkeypatch: pytest.MonkeyPatch,
        strategy: str,
    ) -> None:
        """Ensure unsupported custom kernels are blocked to prevent invalid fast paths."""

        grid = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=int)
        kernel = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=int)

        monkeypatch.setenv("HEART_LIFE_UPDATE_STRATEGY", strategy)

        with pytest.raises(ValueError, match="default kernel"):
            LifeState(grid=grid, kernel=kernel)._update_grid()
