"""Aggregated sensor metrics and reusable event windows."""

from __future__ import annotations

import math
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import (Deque, Dict, Generic, Iterable, Iterator, Mapping,
                    Sequence, TypeVar)

import numpy as np
from scipy.signal import hilbert  # type: ignore[import-untyped]
from scipy.stats import kurtosis  # type: ignore[import-untyped]

T = TypeVar("T")
K = TypeVar("K")


@dataclass(slots=True)
class EventSample(Generic[T]):
    """Timestamped value captured from a sensor."""

    value: T
    timestamp: float


class WindowPolicy(Generic[T]):
    """Strategy for pruning samples held by :class:`EventWindow`."""

    def prune(self, samples: Deque[EventSample[T]], *, now: float) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class MaxLengthPolicy(WindowPolicy[T]):
    """Limit a window to the most recent ``count`` samples."""

    def __init__(self, *, count: int) -> None:
        if count <= 0:
            msg = "count must be a positive integer"
            raise ValueError(msg)
        self._count = count

    def prune(self, samples: Deque[EventSample[T]], *, now: float) -> None:  # noqa: ARG002
        while len(samples) > self._count:
            samples.popleft()


class MaxAgePolicy(WindowPolicy[T]):
    """Limit a window to samples captured within ``window`` seconds."""

    def __init__(self, *, window: float) -> None:
        if window <= 0:
            msg = "window must be a positive duration"
            raise ValueError(msg)
        self._window = window

    def prune(self, samples: Deque[EventSample[T]], *, now: float) -> None:
        cutoff = now - self._window
        while samples and samples[0].timestamp < cutoff:
            samples.popleft()


class EventWindow(Generic[T]):
    """Store the most recent events according to a set of policies."""

    def __init__(self, *, policies: Iterable[WindowPolicy[T]] = ()) -> None:
        self._policies: tuple[WindowPolicy[T], ...] = tuple(policies)
        self._samples: Deque[EventSample[T]] = deque()

    @property
    def policies(self) -> tuple[WindowPolicy[T], ...]:
        return self._policies

    def derive(self, *policies: WindowPolicy[T]) -> "EventWindow[T]":
        """Return a new window with the existing and additional policies."""

        return EventWindow(policies=(*self._policies, *policies))

    def append(self, value: T, *, timestamp: float | None = None) -> None:
        now = time.monotonic() if timestamp is None else timestamp
        self._samples.append(EventSample(value=value, timestamp=now))
        for policy in self._policies:
            policy.prune(self._samples, now=now)

    def extend(self, values: Iterable[T], *, timestamp: float | None = None, step: float = 0.0) -> None:
        """Append multiple values using a shared starting timestamp."""

        now = time.monotonic() if timestamp is None else timestamp
        for index, value in enumerate(values):
            self.append(value, timestamp=now + (index * step))

    def __len__(self) -> int:
        return len(self._samples)

    def __iter__(self) -> Iterator[T]:
        for sample in self._samples:
            yield sample.value

    def samples(self) -> tuple[EventSample[T], ...]:
        return tuple(self._samples)

    def values(self) -> tuple[T, ...]:
        return tuple(sample.value for sample in self._samples)


def combine_windows(*windows: EventWindow[T]) -> EventWindow[T]:
    """Return a new window that enforces the policies from each ``window``."""

    policies: list[WindowPolicy[T]] = []
    for window in windows:
        policies.extend(window.policies)
    return EventWindow(policies=policies)


class LastNEvents(EventWindow[T]):
    """Maintain the last ``count`` events regardless of age."""

    def __init__(self, *, count: int) -> None:
        super().__init__(policies=(MaxLengthPolicy(count=count),))


class LastEventsWithinTimeWindow(EventWindow[T]):
    """Maintain events captured within ``window`` seconds."""

    def __init__(self, *, window: float) -> None:
        super().__init__(policies=(MaxAgePolicy(window=window),))


class LastNEventsWithinTimeWindow(EventWindow[T]):
    """Maintain the last ``count`` events that are newer than ``window`` seconds."""

    def __init__(self, *, count: int, window: float) -> None:
        combined = combine_windows(LastNEvents(count=count), LastEventsWithinTimeWindow(window=window))
        super().__init__(policies=combined.policies)


class CountByKey(Generic[K]):
    """Count observations grouped by ``key``."""

    def __init__(self) -> None:
        self._counts: Counter[K] = Counter()

    def observe(self, key: K, *, amount: int = 1) -> None:
        self._counts[key] += amount

    def get(self, key: K) -> int:
        return self._counts.get(key, 0)

    def snapshot(self) -> Mapping[K, int]:
        return dict(self._counts)

    def reset(self) -> None:
        self._counts.clear()


@dataclass(slots=True)
class RollingSnapshot:
    """Point-in-time view of rolling statistics for a single key."""

    count: int
    mean: float | None
    stddev: float | None


class _RollingState:
    __slots__ = ("samples", "sum", "sum_sq")

    def __init__(self) -> None:
        self.samples: Deque[EventSample[float]] = deque()
        self.sum = 0.0
        self.sum_sq = 0.0

    def append(self, value: float, *, timestamp: float, maxlen: int | None, window: float | None) -> None:
        sample = EventSample(value=value, timestamp=timestamp)
        self.samples.append(sample)
        self.sum += value
        self.sum_sq += value * value
        self._prune(now=timestamp, maxlen=maxlen, window=window)

    def _prune(self, *, now: float, maxlen: int | None, window: float | None) -> None:
        if window is not None:
            cutoff = now - window
            while self.samples and self.samples[0].timestamp < cutoff:
                removed = self.samples.popleft()
                self.sum -= removed.value
                self.sum_sq -= removed.value * removed.value

        if maxlen is not None:
            while len(self.samples) > maxlen:
                removed = self.samples.popleft()
                self.sum -= removed.value
                self.sum_sq -= removed.value * removed.value

    def snapshot(self) -> RollingSnapshot:
        count = len(self.samples)
        if count == 0:
            return RollingSnapshot(count=0, mean=None, stddev=None)

        mean = self.sum / count
        variance = (self.sum_sq / count) - (mean * mean)
        variance = max(0.0, variance)
        stddev = math.sqrt(variance) if count > 1 else None
        return RollingSnapshot(count=count, mean=mean, stddev=stddev)


class RollingStatisticsByKey(Generic[K]):
    """Compute rolling statistics for float samples grouped by key."""

    def __init__(self, *, maxlen: int | None = None, window: float | None = None) -> None:
        if maxlen is not None and maxlen <= 0:
            msg = "maxlen must be a positive integer"
            raise ValueError(msg)
        if window is not None and window <= 0:
            msg = "window must be a positive duration"
            raise ValueError(msg)
        self._maxlen = maxlen
        self._window = window
        self._states: Dict[K, _RollingState] = defaultdict(_RollingState)

    def observe(self, key: K, value: float, *, timestamp: float | None = None) -> None:
        now = time.monotonic() if timestamp is None else timestamp
        state = self._states[key]
        state.append(float(value), timestamp=now, maxlen=self._maxlen, window=self._window)

    def mean(self, key: K) -> float | None:
        snapshot = self._states.get(key)
        if snapshot is None:
            return None
        return snapshot.snapshot().mean

    def stddev(self, key: K) -> float | None:
        snapshot = self._states.get(key)
        if snapshot is None:
            return None
        return snapshot.snapshot().stddev

    def count(self, key: K) -> int:
        snapshot = self._states.get(key)
        if snapshot is None:
            return 0
        return snapshot.snapshot().count

    def snapshot(self) -> Mapping[K, RollingSnapshot]:
        return {key: state.snapshot() for key, state in self._states.items()}

    def reset(self, key: K | None = None) -> None:
        if key is None:
            self._states.clear()
            return
        self._states.pop(key, None)


class RollingAverageByKey(Generic[K]):
    """Rolling mean of float samples grouped by key."""

    def __init__(self, *, maxlen: int | None = None, window: float | None = None) -> None:
        self._stats = RollingStatisticsByKey[K](maxlen=maxlen, window=window)

    def observe(self, key: K, value: float, *, timestamp: float | None = None) -> None:
        self._stats.observe(key, value, timestamp=timestamp)

    def get(self, key: K) -> float | None:
        return self._stats.mean(key)

    def snapshot(self) -> Mapping[K, float | None]:
        return {key: snap.mean for key, snap in self._stats.snapshot().items()}

    def reset(self, key: K | None = None) -> None:
        self._stats.reset(key)


class RollingMeanByKey(RollingAverageByKey[K]):
    """Alias for :class:`RollingAverageByKey`."""


class RollingStddevByKey(Generic[K]):
    """Rolling standard deviation of float samples grouped by key."""

    def __init__(self, *, maxlen: int | None = None, window: float | None = None) -> None:
        self._stats = RollingStatisticsByKey[K](maxlen=maxlen, window=window)

    def observe(self, key: K, value: float, *, timestamp: float | None = None) -> None:
        self._stats.observe(key, value, timestamp=timestamp)

    def get(self, key: K) -> float | None:
        return self._stats.stddev(key)

    def snapshot(self) -> Mapping[K, float | None]:
        return {key: snap.stddev for key, snap in self._stats.snapshot().items()}

    def reset(self, key: K | None = None) -> None:
        self._stats.reset(key)


@dataclass(slots=True)
class EventCountMetric:
    """Number of events captured within the window."""

    count: int


@dataclass(slots=True)
class EventRateMetric:
    """Event rate expressed in events per second."""

    rate: float | None


@dataclass(slots=True)
class RollingSumMetric:
    """Rolling sum of samples."""

    total: float | None


@dataclass(slots=True)
class RollingMinMetric:
    """Rolling minimum of samples."""

    value: float | None


@dataclass(slots=True)
class RollingMaxMetric:
    """Rolling maximum of samples."""

    value: float | None


@dataclass(slots=True)
class PercentilesMetric:
    """Percentile values computed from the window."""

    values: Mapping[str, float]


@dataclass(slots=True)
class HistogramMetric:
    """Histogram counts and associated bin edges."""

    counts: tuple[float, ...]
    bin_edges: tuple[float, ...]


@dataclass(slots=True)
class EWMAMetric:
    """Exponentially weighted moving average."""

    value: float | None


@dataclass(slots=True)
class InterEventIntervalMetric:
    """Descriptive statistics for inter-event intervals."""

    minimum: float | None
    maximum: float | None
    mean: float | None
    stddev: float | None


@dataclass(slots=True)
class ThresholdExceedanceMetric:
    """Count of samples outside provided thresholds."""

    count: int | None


@dataclass(slots=True)
class ZScoreMetric:
    """Z-score of the most recent sample against the window."""

    score: float | None


@dataclass(slots=True)
class PatternDetectionMetric:
    """Count of pattern occurrences within the window."""

    occurrences: int | None


@dataclass(slots=True)
class CrossCorrelationMetric:
    """Cross-correlation coefficient with a reference window."""

    coefficient: float | None


@dataclass(slots=True)
class DominantFrequencyMetric:
    """Dominant frequency detected via FFT."""

    frequency_hz: float | None


@dataclass(slots=True)
class SampleEntropyMetric:
    """Sample entropy of the window."""

    entropy: float | None


@dataclass(slots=True)
class AllanVarianceMetric:
    """Allan variance describing stability over averaging time."""

    variance: float | None


@dataclass(slots=True)
class HurstExponentMetric:
    """Hurst exponent indicating persistence or mean reversion."""

    exponent: float | None


@dataclass(slots=True)
class CrestFactorMetric:
    """Crest factor describing peak-to-RMS ratio."""

    value: float | None


@dataclass(slots=True)
class KurtosisMetric:
    """Kurtosis capturing tail heaviness of the distribution."""

    value: float | None


@dataclass(slots=True)
class PermutationEntropyMetric:
    """Permutation entropy measuring ordinal complexity."""

    entropy: float | None


@dataclass(slots=True)
class SpectralCentroidMetric:
    """Spectral centroid of the power spectrum."""

    frequency_hz: float | None


@dataclass(slots=True)
class SpectralFlatnessMetric:
    """Spectral flatness describing tonality vs. noisiness."""

    flatness: float | None


@dataclass(slots=True)
class SpectralRolloffMetric:
    """Spectral roll-off frequency for the requested percentile."""

    frequency_hz: float | None


@dataclass(slots=True)
class SpectralEntropyMetric:
    """Spectral entropy of the power distribution."""

    entropy: float | None


@dataclass(slots=True)
class SpectralKurtosisMetric:
    """Spectral kurtosis emphasising impulsive behaviour."""

    kurtosis: float | None


@dataclass(slots=True)
class EnvelopeSpectrumPeakMetric:
    """Peak frequency of the envelope spectrum."""

    frequency_hz: float | None


@dataclass(slots=True)
class OrderTrackedAmplitudeMetric:
    """Order-tracked amplitudes keyed by harmonic order."""

    amplitudes: Mapping[int, float] | None


@dataclass(slots=True)
class TeagerKaiserEnergyMetric:
    """Teager–Kaiser energy of the signal."""

    energy: float | None


@dataclass(slots=True)
class HjorthParametersMetric:
    """Hjorth parameters (activity, mobility, complexity)."""

    parameters: Mapping[str, float] | None


@dataclass(slots=True)
class FanoFactorMetric:
    """Fano factor quantifying dispersion of event counts."""

    factor: float | None


@dataclass(slots=True)
class PeripheralMetricsSnapshot:
    """Snapshot of every peripheral metric."""

    event_count: EventCountMetric
    event_rate: EventRateMetric
    rolling_sum: RollingSumMetric
    rolling_min: RollingMinMetric
    rolling_max: RollingMaxMetric
    percentiles: PercentilesMetric
    histogram: HistogramMetric
    ewma: EWMAMetric
    inter_event_intervals: InterEventIntervalMetric
    threshold_exceedance: ThresholdExceedanceMetric
    z_score: ZScoreMetric
    pattern_detection: PatternDetectionMetric
    cross_correlation: CrossCorrelationMetric
    dominant_frequency: DominantFrequencyMetric
    sample_entropy: SampleEntropyMetric
    allan_variance: AllanVarianceMetric
    hurst_exponent: HurstExponentMetric
    crest_factor: CrestFactorMetric
    kurtosis: KurtosisMetric
    permutation_entropy: PermutationEntropyMetric
    spectral_centroid: SpectralCentroidMetric
    spectral_flatness: SpectralFlatnessMetric
    spectral_rolloff: SpectralRolloffMetric
    spectral_entropy: SpectralEntropyMetric
    spectral_kurtosis: SpectralKurtosisMetric
    envelope_spectrum_peak: EnvelopeSpectrumPeakMetric
    order_tracked_amplitude: OrderTrackedAmplitudeMetric
    tkeo_energy: TeagerKaiserEnergyMetric
    hjorth_parameters: HjorthParametersMetric
    fano_factor: FanoFactorMetric


def compute_peripheral_metrics(
    samples: Sequence[EventSample[float]],
    *,
    histogram_bins: int = 20,
    percentiles: Sequence[float] = (50, 90, 99),
    ewma_alpha: float = 0.3,
    thresholds: tuple[float, float] | None = None,
    pattern: Sequence[float] | None = None,
    pattern_tolerance: float = 1e-3,
    reference_samples: Sequence[EventSample[float]] | None = None,
    rolloff_percent: float = 0.95,
    orders: Sequence[int] = (1,),
    order_reference_hz: float | None = None,
    sample_rate: float | None = None,
) -> PeripheralMetricsSnapshot:
    """Compute the requested metrics using existing window helpers."""

    values, timestamps = _extract_arrays(samples)
    reference_values: np.ndarray | None
    reference_timestamps: np.ndarray | None
    if reference_samples is not None:
        reference_values, reference_timestamps = _extract_arrays(reference_samples)
    else:
        reference_values = None
        reference_timestamps = None

    standard = _compute_standard_metrics(
        values,
        timestamps=timestamps,
        histogram_bins=histogram_bins,
        percentiles=percentiles,
        ewma_alpha=ewma_alpha,
        thresholds=thresholds,
    )
    experimental = _compute_experimental_metrics(
        values,
        timestamps=timestamps,
        reference_values=reference_values,
        reference_timestamps=reference_timestamps,
        pattern=pattern,
        pattern_tolerance=pattern_tolerance,
        sample_rate=sample_rate,
    )
    domain = _compute_domain_metrics(values, sample_rate=sample_rate)
    spectral = _compute_spectral_metrics(
        values,
        sample_rate=sample_rate,
        rolloff_percent=rolloff_percent,
        orders=orders,
        order_reference_hz=order_reference_hz,
    )
    snapshot_kwargs: dict[str, object] = {}
    snapshot_kwargs.update(standard)
    snapshot_kwargs.update(experimental)
    snapshot_kwargs.update(domain)
    snapshot_kwargs.update(spectral)
    return PeripheralMetricsSnapshot(**snapshot_kwargs)


def _extract_arrays(
    samples: Sequence[EventSample[float]],
) -> tuple[np.ndarray, np.ndarray]:
    if not samples:
        return np.asarray([]), np.asarray([])
    values = np.fromiter((sample.value for sample in samples), dtype=float)
    timestamps = np.fromiter((sample.timestamp for sample in samples), dtype=float)
    return values, timestamps


def _compute_standard_metrics(
    values: np.ndarray,
    *,
    timestamps: np.ndarray,
    histogram_bins: int,
    percentiles: Sequence[float],
    ewma_alpha: float,
    thresholds: tuple[float, float] | None,
) -> dict[str, object]:
    event_count = int(values.size)
    duration = float(timestamps[-1] - timestamps[0]) if timestamps.size > 1 else 0.0
    event_rate_value = event_count / duration if duration > 0 else None

    rolling_sum_value = float(np.sum(values)) if event_count else None
    rolling_min_value = float(np.min(values)) if event_count else None
    rolling_max_value = float(np.max(values)) if event_count else None
    percentile_values = (
        {f"p{int(p)}": float(np.percentile(values, p)) for p in percentiles}
        if event_count
        else {}
    )
    if histogram_bins > 0 and event_count > 0:
        counts, bin_edges = np.histogram(values, bins=histogram_bins)
        histogram_metric = HistogramMetric(
            counts=tuple(float(count) for count in counts),
            bin_edges=tuple(float(edge) for edge in bin_edges),
        )
    else:
        histogram_metric = HistogramMetric(counts=(), bin_edges=())

    ewma_value = _compute_ewma(values, alpha=ewma_alpha)
    inter_event = _compute_inter_event_intervals(timestamps)
    threshold_count = _count_threshold_exceedances(values, thresholds)

    return {
        "event_count": EventCountMetric(count=event_count),
        "event_rate": EventRateMetric(rate=event_rate_value),
        "rolling_sum": RollingSumMetric(total=rolling_sum_value),
        "rolling_min": RollingMinMetric(value=rolling_min_value),
        "rolling_max": RollingMaxMetric(value=rolling_max_value),
        "percentiles": PercentilesMetric(values=percentile_values),
        "histogram": histogram_metric,
        "ewma": EWMAMetric(value=ewma_value),
        "inter_event_intervals": inter_event,
        "threshold_exceedance": ThresholdExceedanceMetric(count=threshold_count),
    }


def _compute_experimental_metrics(
    values: np.ndarray,
    *,
    timestamps: np.ndarray,
    reference_values: np.ndarray | None,
    reference_timestamps: np.ndarray | None,
    pattern: Sequence[float] | None,
    pattern_tolerance: float,
    sample_rate: float | None,
) -> dict[str, object]:
    if values.size == 0:
        z_score = None
    else:
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=0))
        z_score = float((values[-1] - mean) / std) if std > 0 else None

    pattern_count = _count_pattern_occurrences(values, pattern, pattern_tolerance)

    cross_correlation = None
    if reference_values is not None and reference_timestamps is not None:
        cross_correlation = _compute_cross_correlation(
            values, reference_values, timestamps, reference_timestamps
        )

    dominant_frequency = _compute_dominant_frequency(values, sample_rate)
    sample_entropy = _sample_entropy(values)

    return {
        "z_score": ZScoreMetric(score=z_score),
        "pattern_detection": PatternDetectionMetric(occurrences=pattern_count),
        "cross_correlation": CrossCorrelationMetric(coefficient=cross_correlation),
        "dominant_frequency": DominantFrequencyMetric(frequency_hz=dominant_frequency),
        "sample_entropy": SampleEntropyMetric(entropy=sample_entropy),
    }


def _compute_domain_metrics(
    values: np.ndarray,
    *,
    sample_rate: float | None,
) -> dict[str, object]:
    allan = _allan_variance(values, sample_rate)
    hurst = _hurst_exponent(values)
    crest = _crest_factor(values)
    kurt = float(kurtosis(values, fisher=True, bias=False)) if values.size > 3 else None
    perm_entropy = _permutation_entropy(values)
    return {
        "allan_variance": AllanVarianceMetric(variance=allan),
        "hurst_exponent": HurstExponentMetric(exponent=hurst),
        "crest_factor": CrestFactorMetric(value=crest),
        "kurtosis": KurtosisMetric(value=kurt),
        "permutation_entropy": PermutationEntropyMetric(entropy=perm_entropy),
    }


def _compute_spectral_metrics(
    values: np.ndarray,
    *,
    sample_rate: float | None,
    rolloff_percent: float,
    orders: Sequence[int],
    order_reference_hz: float | None,
) -> dict[str, object]:
    if values.size == 0:
        spectrum = np.asarray([])
        freqs = np.asarray([])
    else:
        spectrum, freqs = _power_spectrum(values, sample_rate)

    centroid = _spectral_centroid(freqs, spectrum)
    flatness = _spectral_flatness(spectrum)
    rolloff = _spectral_rolloff(freqs, spectrum, rolloff_percent)
    entropy = _spectral_entropy(spectrum)
    spec_kurtosis = _spectral_kurtosis(spectrum)
    envelope_peak = _envelope_spectrum_peak(values, sample_rate)
    orders_map = _order_tracked_amplitudes(
        spectrum,
        freqs,
        orders,
        order_reference_hz,
    )
    tkeo = _tkeo_energy(values)
    hjorth = _hjorth_parameters(values)
    fano = _fano_factor(values)

    return {
        "spectral_centroid": SpectralCentroidMetric(frequency_hz=centroid),
        "spectral_flatness": SpectralFlatnessMetric(flatness=flatness),
        "spectral_rolloff": SpectralRolloffMetric(frequency_hz=rolloff),
        "spectral_entropy": SpectralEntropyMetric(entropy=entropy),
        "spectral_kurtosis": SpectralKurtosisMetric(kurtosis=spec_kurtosis),
        "envelope_spectrum_peak": EnvelopeSpectrumPeakMetric(
            frequency_hz=envelope_peak
        ),
        "order_tracked_amplitude": OrderTrackedAmplitudeMetric(amplitudes=orders_map),
        "tkeo_energy": TeagerKaiserEnergyMetric(energy=tkeo),
        "hjorth_parameters": HjorthParametersMetric(parameters=hjorth),
        "fano_factor": FanoFactorMetric(factor=fano),
    }


def _compute_ewma(values: np.ndarray, *, alpha: float) -> float | None:
    if values.size == 0:
        return None
    alpha = float(np.clip(alpha, 0.0, 1.0))
    if alpha == 0:
        return float(values[-1])
    ewma = values[0]
    for value in values[1:]:
        ewma = alpha * value + (1 - alpha) * ewma
    return float(ewma)


def _compute_inter_event_intervals(timestamps: np.ndarray) -> InterEventIntervalMetric:
    if timestamps.size < 2:
        return InterEventIntervalMetric(None, None, None, None)
    deltas = np.diff(timestamps)
    return InterEventIntervalMetric(
        minimum=float(np.min(deltas)),
        maximum=float(np.max(deltas)),
        mean=float(np.mean(deltas)),
        stddev=float(np.std(deltas, ddof=0)),
    )


def _count_threshold_exceedances(
    values: np.ndarray, thresholds: tuple[float, float] | None
) -> int | None:
    if thresholds is None:
        return None
    lower, upper = thresholds
    exceedances = np.logical_or(values < lower, values > upper)
    return int(np.count_nonzero(exceedances))


def _count_pattern_occurrences(
    values: np.ndarray,
    pattern: Sequence[float] | None,
    tolerance: float,
) -> int | None:
    if pattern is None or len(pattern) == 0:
        return None
    pattern_arr = np.asarray(pattern, dtype=float)
    if values.size < pattern_arr.size:
        return 0

    count = 0
    for start in range(values.size - pattern_arr.size + 1):
        window = values[start : start + pattern_arr.size]
        if np.all(np.abs(window - pattern_arr) <= tolerance):
            count += 1
    return count


def _compute_cross_correlation(
    primary: np.ndarray,
    reference: np.ndarray,
    primary_timestamps: np.ndarray,
    reference_timestamps: np.ndarray,
) -> float | None:
    if primary.size == 0 or reference.size == 0:
        return None
    primary_mean = primary - np.mean(primary)
    reference_mean = reference - np.mean(reference)
    correlation = np.correlate(primary_mean, reference_mean, mode="valid")
    denom = np.linalg.norm(primary_mean) * np.linalg.norm(reference_mean)
    if denom == 0:
        return None
    return float(correlation[0] / denom)


def _compute_dominant_frequency(values: np.ndarray, sample_rate: float | None) -> float | None:
    if values.size == 0 or sample_rate is None or sample_rate <= 0:
        return None
    spectrum = np.abs(np.fft.rfft(values))
    freqs = np.fft.rfftfreq(values.size, d=1.0 / sample_rate)
    max_index = np.argmax(spectrum[1:]) + 1 if spectrum.size > 1 else 0
    return float(freqs[max_index])


def _sample_entropy(values: np.ndarray, m: int = 2, r: float | None = None) -> float | None:
    if values.size <= m + 1:
        return None
    if r is None:
        r = 0.2 * np.std(values, ddof=0)
    if r == 0:
        return None
    count = 0
    template_count = 0
    limit = values.size - m
    for i in range(limit):
        template = values[i : i + m]
        for j in range(i + 1, limit):
            window = values[j : j + m]
            if np.max(np.abs(template - window)) <= r:
                template_count += 1
                if abs(values[i + m] - values[j + m]) <= r:
                    count += 1
    if template_count == 0 or count == 0:
        return 0.0
    return float(-np.log(count / template_count))


def _allan_variance(values: np.ndarray, sample_rate: float | None) -> float | None:
    if values.size < 2 or sample_rate is None or sample_rate <= 0:
        return None
    taus = np.array([1, 2, 4, 8]) / sample_rate
    variances = []
    for tau in taus:
        m = int(round(tau * sample_rate))
        if m < 1 or 2 * m >= values.size:
            continue
        averaged = np.array([np.mean(values[i : i + m]) for i in range(0, values.size - m + 1)])
        diff = np.diff(averaged)
        if diff.size == 0:
            continue
        variances.append(0.5 * np.mean(diff**2))
    if not variances:
        return None
    return float(np.mean(variances))


def _hurst_exponent(values: np.ndarray) -> float | None:
    if values.size < 20:
        return None
    cumulative = np.cumsum(values - np.mean(values))
    ranges = np.max(cumulative) - np.min(cumulative)
    std = np.std(values, ddof=0)
    if std == 0 or ranges == 0:
        return None
    return float(np.log(ranges / std) / np.log(values.size))


def _crest_factor(values: np.ndarray) -> float | None:
    if values.size == 0:
        return None
    rms = np.sqrt(np.mean(values**2))
    if rms == 0:
        return None
    peak = np.max(np.abs(values))
    return float(peak / rms)


def _permutation_entropy(values: np.ndarray, order: int = 3) -> float | None:
    if values.size < order:
        return None
    patterns = {}
    for i in range(values.size - order + 1):
        pattern = tuple(np.argsort(values[i : i + order]))
        patterns[pattern] = patterns.get(pattern, 0) + 1
    counts = np.array(list(patterns.values()), dtype=float)
    probabilities = counts / np.sum(counts)
    return float(-np.sum(probabilities * np.log(probabilities)))


def _power_spectrum(values: np.ndarray, sample_rate: float | None) -> tuple[np.ndarray, np.ndarray]:
    if sample_rate is None or sample_rate <= 0:
        sample_rate = 1.0
    spectrum = np.abs(np.fft.rfft(values)) ** 2
    freqs = np.fft.rfftfreq(values.size, d=1.0 / sample_rate)
    return spectrum, freqs


def _spectral_centroid(freqs: np.ndarray, spectrum: np.ndarray) -> float | None:
    if spectrum.size == 0 or np.sum(spectrum) == 0:
        return None
    return float(np.sum(freqs * spectrum) / np.sum(spectrum))


def _spectral_flatness(spectrum: np.ndarray) -> float | None:
    if spectrum.size == 0:
        return None
    geometric_mean = np.exp(np.mean(np.log(np.maximum(spectrum, 1e-12))))
    arithmetic_mean = np.mean(spectrum)
    if arithmetic_mean == 0:
        return None
    return float(geometric_mean / arithmetic_mean)


def _spectral_rolloff(
    freqs: np.ndarray,
    spectrum: np.ndarray,
    rolloff_percent: float,
) -> float | None:
    if spectrum.size == 0:
        return None
    cumulative = np.cumsum(spectrum)
    target = rolloff_percent * cumulative[-1]
    index = np.searchsorted(cumulative, target)
    index = min(index, freqs.size - 1)
    return float(freqs[index])


def _spectral_entropy(spectrum: np.ndarray) -> float | None:
    if spectrum.size == 0:
        return None
    norm = np.sum(spectrum)
    if norm == 0:
        return None
    probabilities = spectrum / norm
    return float(-np.sum(probabilities * np.log(probabilities + 1e-12)))


def _spectral_kurtosis(spectrum: np.ndarray) -> float | None:
    if spectrum.size < 4:
        return None
    centered = spectrum - np.mean(spectrum)
    variance = np.mean(centered**2)
    if variance == 0:
        return None
    return float(np.mean(centered**4) / (variance**2))


def _envelope_spectrum_peak(values: np.ndarray, sample_rate: float | None) -> float | None:
    if sample_rate is None or sample_rate <= 0:
        return None
    analytic_signal = hilbert(values)
    envelope = np.abs(analytic_signal)
    spectrum = np.abs(np.fft.rfft(envelope))
    freqs = np.fft.rfftfreq(envelope.size, d=1.0 / sample_rate)
    peak_index = int(np.argmax(spectrum))
    return float(freqs[peak_index])


def _order_tracked_amplitudes(
    spectrum: np.ndarray,
    freqs: np.ndarray,
    orders: Sequence[int],
    reference_hz: float | None,
) -> Mapping[int, float] | None:
    if reference_hz is None or reference_hz <= 0 or not orders:
        return None
    amplitudes: dict[int, float] = {}
    for order in orders:
        target_freq = order * reference_hz
        index = int(np.argmin(np.abs(freqs - target_freq)))
        amplitudes[order] = float(spectrum[index]) if index < spectrum.size else 0.0
    return amplitudes


def _tkeo_energy(values: np.ndarray) -> float | None:
    if values.size < 3:
        return None
    energy = values[1:-1] ** 2 - values[:-2] * values[2:]
    return float(np.mean(energy))


def _hjorth_parameters(values: np.ndarray) -> Mapping[str, float] | None:
    if values.size < 3:
        return None
    activity = float(np.var(values))
    diff = np.diff(values)
    diff2 = np.diff(diff)
    mobility = float(np.sqrt(np.var(diff) / activity)) if activity > 0 else 0.0
    complexity = float(np.sqrt(np.var(diff2) / np.var(diff))) if np.var(diff) > 0 else 0.0
    return {"activity": activity, "mobility": mobility, "complexity": complexity}


def _fano_factor(values: np.ndarray) -> float | None:
    if values.size == 0:
        return None
    mean = float(np.mean(values))
    if abs(mean) < 1e-12:
        return None
    variance = float(np.var(values))
    return variance / mean


__all__ = [
    "AllanVarianceMetric",
    "CountByKey",
    "CrestFactorMetric",
    "CrossCorrelationMetric",
    "DominantFrequencyMetric",
    "EnvelopeSpectrumPeakMetric",
    "EventCountMetric",
    "EventRateMetric",
    "EventSample",
    "EventWindow",
    "EWMAMetric",
    "FanoFactorMetric",
    "HistogramMetric",
    "HjorthParametersMetric",
    "HurstExponentMetric",
    "InterEventIntervalMetric",
    "KurtosisMetric",
    "LastEventsWithinTimeWindow",
    "LastNEvents",
    "LastNEventsWithinTimeWindow",
    "MaxAgePolicy",
    "MaxLengthPolicy",
    "OrderTrackedAmplitudeMetric",
    "PatternDetectionMetric",
    "PeripheralMetricsSnapshot",
    "PercentilesMetric",
    "PermutationEntropyMetric",
    "RollingAverageByKey",
    "RollingMaxMetric",
    "RollingMeanByKey",
    "RollingMinMetric",
    "RollingSnapshot",
    "RollingStatisticsByKey",
    "RollingStddevByKey",
    "RollingSumMetric",
    "SampleEntropyMetric",
    "SpectralCentroidMetric",
    "SpectralEntropyMetric",
    "SpectralFlatnessMetric",
    "SpectralKurtosisMetric",
    "SpectralRolloffMetric",
    "TeagerKaiserEnergyMetric",
    "ThresholdExceedanceMetric",
    "ZScoreMetric",
    "combine_windows",
    "compute_peripheral_metrics",
]
