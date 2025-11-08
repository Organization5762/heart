from typing import Iterable

import numpy as np
import pytest

from heart.events.metrics import EventSample, compute_peripheral_metrics


def _samples(values: Iterable[float], *, start: float = 0.0, step: float = 1.0):
    return [
        EventSample(value=float(value), timestamp=start + index * step)
        for index, value in enumerate(values)
    ]


def test_compute_peripheral_metrics_standard_fields() -> None:
    samples = _samples([1.0, 2.0, 3.0, 4.0], step=0.5)
    snapshot = compute_peripheral_metrics(
        samples,
        histogram_bins=2,
        percentiles=(50, 75),
        ewma_alpha=1.0,
        thresholds=(0.0, 3.0),
    )

    assert snapshot.event_count.count == 4
    assert snapshot.event_rate.rate == pytest.approx(4 / 1.5)
    assert snapshot.rolling_sum.total == pytest.approx(10.0)
    assert snapshot.rolling_min.value == pytest.approx(1.0)
    assert snapshot.rolling_max.value == pytest.approx(4.0)
    assert snapshot.percentiles.values["p50"] == pytest.approx(2.5)
    assert "p75" in snapshot.percentiles.values
    histogram = snapshot.histogram
    assert histogram.counts
    assert sum(histogram.counts) == pytest.approx(4.0)
    assert snapshot.ewma.value == pytest.approx(4.0)

    intervals = snapshot.inter_event_intervals
    assert intervals.minimum == pytest.approx(0.5)
    assert intervals.maximum == pytest.approx(0.5)
    assert intervals.mean == pytest.approx(0.5)
    assert intervals.stddev == pytest.approx(0.0)

    assert snapshot.threshold_exceedance.count == 1


def test_compute_peripheral_metrics_experimental_fields() -> None:
    values = [0.0, 1.0, 0.0, -1.0, 0.0]
    samples = _samples(values, step=0.1)
    reference = _samples(values, step=0.1)

    snapshot = compute_peripheral_metrics(
        samples,
        reference_samples=reference,
        pattern=(0.0, 1.0, 0.0),
        pattern_tolerance=1e-6,
        sample_rate=10.0,
    )

    assert snapshot.pattern_detection.occurrences == 1
    assert snapshot.cross_correlation.coefficient == pytest.approx(1.0)
    assert snapshot.dominant_frequency.frequency_hz == pytest.approx(2.0, rel=0.1)
    assert snapshot.sample_entropy.entropy is not None


def test_compute_peripheral_metrics_domain_and_spectral_fields() -> None:
    sample_rate = 100.0
    duration = 1.0
    t = np.arange(0.0, duration, 1.0 / sample_rate)
    freq = 5.0
    waveform = np.sin(2 * np.pi * freq * t)
    samples = _samples(waveform, step=1.0 / sample_rate)

    snapshot = compute_peripheral_metrics(
        samples,
        sample_rate=sample_rate,
        rolloff_percent=0.9,
        orders=(1, 2),
        order_reference_hz=freq,
    )

    assert snapshot.allan_variance.variance is not None
    assert snapshot.hurst_exponent.exponent is not None
    assert snapshot.crest_factor.value == pytest.approx(1.414, rel=0.05)
    assert snapshot.kurtosis.value is not None
    assert snapshot.permutation_entropy.entropy is not None

    assert snapshot.spectral_centroid.frequency_hz == pytest.approx(freq, rel=0.1)
    assert snapshot.spectral_flatness.flatness is not None
    assert snapshot.spectral_rolloff.frequency_hz is not None
    assert snapshot.spectral_entropy.entropy is not None
    assert snapshot.spectral_kurtosis.kurtosis is not None
    assert snapshot.envelope_spectrum_peak.frequency_hz == pytest.approx(0.0, abs=1e-6)
    assert snapshot.order_tracked_amplitude.amplitudes is not None
    assert snapshot.order_tracked_amplitude.amplitudes[1] == pytest.approx(
        snapshot.order_tracked_amplitude.amplitudes[1]
    )
    assert snapshot.tkeo_energy.energy is not None
    assert snapshot.hjorth_parameters.parameters is not None
    assert snapshot.fano_factor.factor is None


def test_compute_peripheral_metrics_handles_empty_samples() -> None:
    snapshot = compute_peripheral_metrics(())
    assert snapshot.event_count.count == 0
    assert snapshot.z_score.score is None
    assert snapshot.crest_factor.value is None
    assert snapshot.spectral_entropy.entropy is None
