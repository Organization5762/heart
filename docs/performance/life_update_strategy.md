# Life Module Update Strategy

## Problem Statement

Reduce the per-frame cost of the Game of Life update while keeping the rules identical to the existing convolution-based implementation.

## Materials

- Python environment with `numpy` and `scipy` installed.
- `heart.modules.life.state.LifeState` for the update loop.
- `heart.utilities.env.Configuration` for environment-driven settings.

## Update Strategy Options

The Life module supports selecting the update algorithm via environment variable:

- `HEART_LIFE_UPDATE_STRATEGY=auto` (default) uses a padding-based neighbor count when the default kernel is in use.
- `HEART_LIFE_UPDATE_STRATEGY=convolve` always uses `scipy.ndimage.convolve`.
- `HEART_LIFE_UPDATE_STRATEGY=pad` forces the padding-based neighbor count, which only supports the default kernel.

## Operational Notes

- Padding-based updates avoid convolution setup overhead while preserving the same rules on the same grid boundaries.
- When using custom kernels, keep the strategy at `auto` or `convolve` so the kernel is applied correctly.
