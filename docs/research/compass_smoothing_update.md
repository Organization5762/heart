______________________________________________________________________

## title: Compass smoothing performance update

# Compass smoothing performance update

## Summary

The compass peripheral now supports a configurable smoothing strategy and
avoids recomputing rolling averages by tracking a running sum of recent
magnetometer samples. This reduces per-sample work while still exposing an
EMA option for faster response when noise levels are lower.

## Sources

- `src/heart/peripheral/compass.py` (smoothing logic, running-sum tracking, EMA updates)
- `src/heart/utilities/env.py` (environment variable configuration)

## Materials

- Environment variables: `HEART_COMPASS_SMOOTHING`,
  `HEART_COMPASS_WINDOW_SIZE`, `HEART_COMPASS_EMA_ALPHA`.
