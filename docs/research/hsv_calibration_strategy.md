# HSV calibration strategy options

The numpy HSV/BGR fallback path in `src/heart/environment.py` performs a
neighbourhood search when its float-based conversion is off by a small amount.
That search used a per-pixel loop, which could become expensive on larger
frames. The calibration strategy selector exposes the newer vectorized search
so deployments can opt into the faster path or keep the legacy loop when
necessary.

## Observations

- The new vectorized strategy batches the 3x3x3 neighbourhood candidates for
  each mismatched pixel and compares them to the target HSV values in one numpy
  call.
- The legacy strategy retains the nested loop for cases where byte-for-byte
  parity with historical behaviour is required.
- `HEART_HSV_CALIBRATION_STRATEGY` allows switching strategies without changing
  call sites or feature flags.

## Materials

- Environment variables: `HEART_HSV_CALIBRATION`,
  `HEART_HSV_CALIBRATION_STRATEGY`.
- Source: `src/heart/environment.py`, `src/heart/utilities/env.py`.
