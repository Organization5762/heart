# Signal cross-correlation FFT tuning

## Summary

The cross-correlation helper in `heart.utilities.signal` uses FFT-based
convolution when the input sizes are large enough. The previous
implementation always used an FFT length equal to the exact correlation
length, which can be slower than padding to a power of two for large
inputs. This note records the change to allow configurable FFT padding
and thresholding so deployments can choose between compatibility and
throughput.

## Implementation notes

- `heart.utilities.signal._fft_cross_correlation` now pads to the next
  power of two by default before calling `numpy.fft.rfft`.
- The padding behaviour is configurable with
  `HEART_SIGNAL_FFT_PAD_MODE` (`next_pow2` or `exact`).
- The FFT switch-over threshold is configurable with
  `HEART_SIGNAL_FFT_THRESHOLD` so devices can force or defer the FFT path
  depending on CPU budget.

## Operational guidance

- Use `HEART_SIGNAL_FFT_PAD_MODE=exact` if the FFT padding change needs
  to be disabled for troubleshooting or performance comparisons.
- Adjust `HEART_SIGNAL_FFT_THRESHOLD` upward if the FFT path adds
  overhead for short sequences, or downward if workloads routinely
  exceed the default size.

## Materials

- `src/heart/utilities/signal.py`
- `src/heart/utilities/env.py`
- `tests/utilities/test_signal.py`
