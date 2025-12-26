from __future__ import annotations

import pytest

from heart.derive import layout


class TestClusterPositions:
    """Validate cluster grouping behaviour that keeps axis buckets distinct."""

    @pytest.mark.parametrize(
        ("values", "tolerance", "expected"),
        [
            pytest.param(
                [0.0, 0.5, 1.0],
                0.6,
                [0.25, 1.0],
                id="blocks_transitive_merge",
            ),
            pytest.param(
                [0.0, 0.2, 0.4],
                0.5,
                [0.2],
                id="single_cluster_within_span",
            ),
        ],
    )
    def test_cluster_positions_respects_span_limit(
        self,
        values: list[float],
        tolerance: float,
        expected: list[float],
    ) -> None:
        """Ensure clusters cap their span to avoid collapsing distinct rows/columns."""
        clustered = layout._cluster_positions(values, tolerance)

        assert clustered == pytest.approx(expected)
