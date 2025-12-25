# Life Module Update Strategy

## Problem Statement

Reduce the per-frame cost of the Game of Life update while keeping the rules identical to the existing convolution-based implementation.

## Materials

- Python environment with `numpy` and `scipy` installed.
- `heart.renderers.life.state.LifeState` for the update loop.
- `heart.utilities.env.Configuration` for environment-driven settings.

## Update Strategy Options

The Life module supports selecting the neighbor-count update algorithm via environment variable:

- `HEART_LIFE_UPDATE_STRATEGY=auto` (default) uses a slice-based neighbor count for the default kernel unless a
  convolution threshold is configured.
- `HEART_LIFE_UPDATE_STRATEGY=convolve` always uses `scipy.ndimage.convolve`.
- `HEART_LIFE_UPDATE_STRATEGY=pad` forces the padding-based neighbor count, which only supports the default kernel.
- `HEART_LIFE_UPDATE_STRATEGY=shifted` uses a slice-based neighbor count for the default kernel only.

`HEART_LIFE_CONVOLVE_THRESHOLD` (default `0`) optionally switches `auto` to convolution when the grid size
meets or exceeds the configured cell count. Set it to a positive integer to prefer convolution for large
grids while keeping the slice-based path for smaller updates.

## Rule Application Options

Rule application can be configured separately from neighbor counting:

- `HEART_LIFE_RULE_STRATEGY=auto` (default) selects the table lookup when the default kernel is used and
  neighbor counts remain within the 0-8 range, falling back to boolean rules otherwise.
- `HEART_LIFE_RULE_STRATEGY=direct` always applies the boolean rules.
- `HEART_LIFE_RULE_STRATEGY=table` prefers the table lookup but falls back to boolean rules if custom
  kernels or unexpected neighbor counts are detected.

`HEART_LIFE_RANDOM_SEED` optionally pins the RNG used by the Life renderer for reproducible initial and
reseeded grids.

## Operational Notes

- Slice-based updates avoid repeated padding allocations while preserving the same rules on the same grid boundaries.
- Padding-based updates are still available if you want to preserve the original neighbor count implementation.
- When using custom kernels, keep the strategy at `auto` or `convolve` so the kernel is applied correctly.
