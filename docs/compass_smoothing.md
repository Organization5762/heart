______________________________________________________________________

## title: Compass smoothing configuration

# Compass smoothing configuration

## Problem

Compass headings can jitter when raw magnetometer samples vary quickly. The
compass peripheral now supports multiple smoothing algorithms so deployments
can balance responsiveness against stability based on their noise profile.

## Configuration

Set these environment variables to tune the compass smoothing behaviour:

- `HEART_COMPASS_SMOOTHING` controls the smoothing algorithm.
  - `window` (default) computes a rolling mean across the window.
  - `ema` applies an exponential moving average.
- `HEART_COMPASS_WINDOW_SIZE` sets the number of samples in the rolling mean
  window (default: `5`, minimum: `1`). This is only used when
  `HEART_COMPASS_SMOOTHING=window`.
- `HEART_COMPASS_EMA_ALPHA` sets the EMA blend factor (default: `0.2`,
  range: `(0.0, 1.0]`). Higher values respond faster but reduce smoothing.

## Implementation notes

- Window smoothing maintains a running sum to avoid recomputing the total
  on every sample update.
- EMA smoothing stores the current smoothed vector and blends in new samples.

## Materials

- Magnetometer sample stream (`peripheral.magnetometer.vector` payloads).
- Environment variables: `HEART_COMPASS_SMOOTHING`,
  `HEART_COMPASS_WINDOW_SIZE`, `HEART_COMPASS_EMA_ALPHA`.
