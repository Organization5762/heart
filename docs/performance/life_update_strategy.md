# Life Module Update Strategy

## Problem Statement

Reduce the per-frame cost of the Game of Life update while keeping the rules identical to the existing convolution-based implementation.

## Materials

- Python environment with `numpy` and `scipy` installed.
- `heart.renderers.life.state.LifeState` for the update loop.
- `heart.utilities.env.Configuration` for environment-driven settings.

## Update Strategy Options

The Life module supports selecting the update algorithm via environment variable:

- `HEART_LIFE_UPDATE_STRATEGY=auto` (default) uses a slice-based neighbor count for the default kernel unless a
  convolution threshold is configured.
- `HEART_LIFE_UPDATE_STRATEGY=convolve` always uses `scipy.ndimage.convolve`.
- `HEART_LIFE_UPDATE_STRATEGY=pad` forces the padding-based neighbor count, which only supports the default kernel.
- `HEART_LIFE_UPDATE_STRATEGY=shifted` uses a slice-based neighbor count for the default kernel only.

`HEART_LIFE_CONVOLVE_THRESHOLD` (default `0`) optionally switches `auto` to convolution when the grid size
meets or exceeds the configured cell count. Set it to a positive integer to prefer convolution for large
grids while keeping the slice-based path for smaller updates.

## Rule Application Options

The Life module also supports selecting the rule-application path independently of neighbor counting:

- `HEART_LIFE_RULE_STRATEGY=auto` (default) uses the table-driven rule path for the default kernel and falls
  back to direct rule evaluation when custom kernels are provided.
- `HEART_LIFE_RULE_STRATEGY=direct` always applies the rules with boolean comparisons.
- `HEART_LIFE_RULE_STRATEGY=table` uses a lookup table when valid, falling back to direct evaluation if the
  neighbor counts are outside the standard 0-8 range.

`HEART_LIFE_RANDOM_SEED` optionally sets the RNG seed used when generating new Life grids so initial states
and reseeds can be reproduced.

## Operational Notes

- Slice-based updates avoid repeated padding allocations while preserving the same rules on the same grid boundaries.
- Padding-based updates are still available if you want to preserve the original neighbor count implementation.
- When using custom kernels, keep the strategy at `auto` or `convolve` so the kernel is applied correctly.
- Table-driven rule application is safe for the default kernel; custom kernels automatically fall back to the
  direct path so rule evaluation remains correct.
