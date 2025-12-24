# Life Module Update Strategy Research Note

## Problem Statement

The Game of Life update in `heart.modules.life.state.LifeState` relied on a convolution-based neighbor count. This note captures the alternative padding-based neighbor count used to reduce per-frame overhead while keeping the same update rules.

## Materials

- `src/heart/modules/life/state.py` for the update logic and neighbor counting.
- `src/heart/utilities/env.py` for configuration via environment variables.
- `tests/modules/test_life_state.py` for parity checks between strategies.

## Findings

- A padding-based neighbor count using `numpy.pad` and slice summation matches the convolution result when the default kernel is used.
- The padding strategy is suitable for the default Moore neighborhood but is not compatible with custom kernels, so configuration must guard that case.

## Source Pointers

- Neighbor counting logic: `heart.modules.life.state._count_neighbors_with_padding`.
- Strategy selection: `heart.modules.life.state.LifeState._update_grid`.
- Configuration entry point: `heart.utilities.env.Configuration.life_update_strategy`.
