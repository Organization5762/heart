# Research Note: Faster cross-correlation for signal utilities

## Problem statement

`heart.utilities.signal.cross_correlation` relied on `numpy.correlate`, which uses an
O(N×M) implementation. When the reference and comparison buffers grow large, this
cost becomes noticeable in metrics pipelines that call the function repeatedly.

## Proposed change

Use an FFT-based correlation path for large inputs while keeping the existing
direct method for smaller sequences. The FFT path computes the correlation as a
convolution of the centered reference with the reversed centered comparison,
which preserves the lag ordering returned by `numpy.correlate(mode="full")`.

## Implementation notes

- Added `_fft_cross_correlation` in `src/heart/utilities/signal.py` to compute the
  FFT-based correlation.
- Introduced a size threshold to decide when to use FFTs versus the direct
  `numpy.correlate` path.

## Materials

- `src/heart/utilities/signal.py` (`cross_correlation`, `_fft_cross_correlation`)
