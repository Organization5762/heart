# Life Module Update Strategy

## Problem Statement

Reduce the per-frame cost of the Game of Life update while keeping the rules identical to the existing convolution-based implementation.

## Materials

- Python environment with `numpy` and `scipy` installed.
- `heart.modules.life.state.LifeState` for the update loop.
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

## Operational Notes

- Slice-based updates avoid repeated padding allocations while preserving the same rules on the same grid boundaries.
- Padding-based updates are still available if you want to preserve the original neighbor count implementation.
- When using custom kernels, keep the strategy at `auto` or `convolve` so the kernel is applied correctly.
