"""Signal processing helpers shared across metrics implementations."""

from __future__ import annotations

from importlib import import_module
from typing import Callable, Sequence

import numpy as np

_scipy_hilbert: Callable[[np.ndarray], np.ndarray] | None = None


def _load_scipy_hilbert() -> Callable[[np.ndarray], np.ndarray] | None:
    global _scipy_hilbert
    if _scipy_hilbert is not None:
        return _scipy_hilbert
    try:  # pragma: no cover - optional dependency
        module = import_module("scipy.signal")
        hilbert_fn = getattr(module, "hilbert", None)
    except Exception:  # pragma: no cover - optional dependency
        hilbert_fn = None
    if callable(hilbert_fn):
        _scipy_hilbert = hilbert_fn
    else:
        _scipy_hilbert = None
    return _scipy_hilbert


def _as_array(samples: Sequence[float] | np.ndarray) -> np.ndarray:
    array = np.asarray(samples, dtype=float)
    if array.ndim != 1:
        msg = "samples must be a one-dimensional sequence"
        raise ValueError(msg)
    return array


def fft_magnitude(samples: Sequence[float], *, sample_rate: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return frequency bins and magnitudes using an FFT."""

    array = _as_array(samples)
    if array.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)
    spectrum = np.fft.rfft(array)
    magnitudes = np.abs(spectrum) / array.size
    freqs = np.fft.rfftfreq(array.size, d=(1.0 / sample_rate) if sample_rate else 1.0)
    return freqs, magnitudes


def hilbert_envelope(samples: Sequence[float]) -> np.ndarray:
    """Compute the magnitude envelope using a Hilbert transform."""

    array = _as_array(samples)
    if array.size == 0:
        return np.array([], dtype=float)
    hilbert_fn = _load_scipy_hilbert()
    if hilbert_fn is not None:
        analytic = hilbert_fn(array)
        return np.abs(analytic)
    spectrum = np.fft.fft(array)
    h = np.zeros(array.size)
    if array.size > 0:
        h[0] = 1
        half = (array.size + 1) // 2
        h[1:half] = 2
        if array.size % 2 == 0:
            h[half] = 1
    analytic = np.fft.ifft(spectrum * h)
    return np.abs(analytic)


def cross_correlation(
    reference: Sequence[float],
    comparison: Sequence[float],
    *,
    normalise: bool = True,
    max_lag: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return lags and correlation scores between two sequences."""

    ref = _as_array(reference)
    comp = _as_array(comparison)
    if ref.size == 0 or comp.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)
    ref_centered = ref - ref.mean()
    comp_centered = comp - comp.mean()
    correlation = np.correlate(ref_centered, comp_centered, mode="full")
    lags = np.arange(-comp.size + 1, ref.size)
    if max_lag is not None:
        mask = np.abs(lags) <= max_lag
        lags = lags[mask]
        correlation = correlation[mask]
    if normalise:
        denom = np.linalg.norm(ref_centered) * np.linalg.norm(comp_centered)
        if denom > 0:
            correlation = correlation / denom
    return lags.astype(float), correlation.astype(float)


def dominant_frequency(samples: Sequence[float], *, sample_rate: float) -> tuple[float, float]:
    """Return the dominant frequency bin (Hz) and its magnitude."""

    freqs, magnitudes = fft_magnitude(samples, sample_rate=sample_rate)
    if magnitudes.size == 0:
        return 0.0, 0.0
    index = int(np.argmax(magnitudes))
    return float(freqs[index]), float(magnitudes[index])
