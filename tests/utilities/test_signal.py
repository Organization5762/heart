from __future__ import annotations

import math

import numpy as np
import pytest

from heart.utilities.signal import (cross_correlation, dominant_frequency,
                                    fft_magnitude, hilbert_envelope)


class TestUtilitiesSignal:
    """Group Utilities Signal tests so utilities signal behaviour stays reliable. This preserves confidence in utilities signal for end-to-end scenarios."""

    def test_fft_magnitude_identifies_peak(self) -> None:
        """Verify that fft magnitude identifies peak. This supports analytics accuracy for monitoring."""
        sample_rate = 100.0
        duration = 1.0
        t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)
        samples = np.sin(2 * math.pi * 5.0 * t)
        freqs, magnitudes = fft_magnitude(samples, sample_rate=sample_rate)
        peak_frequency = freqs[int(np.argmax(magnitudes))]
        assert peak_frequency == 5.0



    def test_dominant_frequency_matches_fft(self) -> None:
        """Verify that dominant frequency matches fft. This supports analytics accuracy for monitoring."""
        sample_rate = 200.0
        t = np.linspace(0.0, 1.0, int(sample_rate), endpoint=False)
        samples = 0.5 * np.sin(2 * math.pi * 20.0 * t)
        frequency, magnitude = dominant_frequency(samples, sample_rate=sample_rate)
        assert frequency == 20.0
        assert magnitude > 0.0



    def test_cross_correlation_detects_zero_lag(self) -> None:
        """Verify that cross correlation detects zero lag. This supports analytics accuracy for monitoring."""
        a = np.array([1.0, 2.0, 3.0, 4.0])
        b = np.array([1.0, 2.0, 3.0, 4.0])
        lags, correlation = cross_correlation(a, b)
        zero_index = int(np.where(lags == 0)[0][0])
        assert correlation[zero_index] == pytest.approx(1.0)



    def test_hilbert_envelope_matches_absolute_for_constant(self) -> None:
        """Verify that hilbert envelope matches absolute for constant. This keeps the system behaviour reliable for operators."""
        samples = np.ones(32)
        envelope = hilbert_envelope(samples)
        assert envelope.shape == samples.shape
        assert np.allclose(envelope, samples)
