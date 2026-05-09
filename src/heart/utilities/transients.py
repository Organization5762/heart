"""Transient analysis helpers for exploratory beat and onset work."""

from __future__ import annotations

from collections import deque
import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import ndimage, signal

DEFAULT_FRAME_SIZE = 1024
DEFAULT_HOP_SIZE = 256
DEFAULT_THRESHOLD_WINDOW_SECONDS = 1.5
DEFAULT_THRESHOLD_SCALE = 2.0 / 3.0
DEFAULT_MIN_SPACING_MS = 140.0
DEFAULT_SUPPRESSION_WINDOW_SECONDS = 0.24
DEFAULT_BPM_MIN = 90.0
DEFAULT_BPM_MAX = 180.0
DEFAULT_RANGE_START_HZ = 25.0
DEFAULT_RANGE_STEP_HZ = 15.0
DEFAULT_RANGE_WIDTH_HZ = 50.0
DEFAULT_RANGE_COUNT = 10
DEFAULT_RECENT_PEAK_COUNT = 3

_EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class Transient:
    """A detected transient candidate."""

    frame_index: int
    time_seconds: float
    strength: float
    low_band_share: float
    high_band_share: float
    centroid_hz: float
    flatness: float


@dataclass(frozen=True, slots=True)
class TransientAnalysis:
    """Outputs from a transient analysis pass."""

    sample_rate: int
    frame_size: int
    hop_size: int
    duration_seconds: float
    band_low_hz: float
    band_high_hz: float
    estimated_bpm: float | None
    bpm_consistency: float
    frame_times: np.ndarray
    low_band_energy: np.ndarray
    raw_flux: np.ndarray
    onset_envelope: np.ndarray
    threshold: np.ndarray
    transients: tuple[Transient, ...]


@dataclass(frozen=True, slots=True)
class TempoCandidate:
    tempo_bpm: int
    count: int


@dataclass(frozen=True, slots=True)
class BandSummary:
    low_hz: float
    high_hz: float
    transient_count: int
    estimated_bpm: float | None
    bpm_consistency: float
    score: float
    tempo_candidates: tuple[TempoCandidate, ...]


def _build_frequency_ranges() -> tuple[tuple[float, float], ...]:
    return tuple(
        (
            DEFAULT_RANGE_START_HZ + (index * DEFAULT_RANGE_STEP_HZ),
            DEFAULT_RANGE_START_HZ
            + (index * DEFAULT_RANGE_STEP_HZ)
            + DEFAULT_RANGE_WIDTH_HZ,
        )
        for index in range(DEFAULT_RANGE_COUNT)
    )


def _group_neighbors_by_tempo(
    peak_times: np.ndarray,
    *,
    bpm_min: float = DEFAULT_BPM_MIN,
    bpm_max: float = DEFAULT_BPM_MAX,
    neighbor_count: int = 10,
) -> tuple[TempoCandidate, ...]:
    tempo_counts: dict[int, int] = {}
    if peak_times.size < 2:
        return ()

    for index, peak_time in enumerate(peak_times):
        for offset in range(1, min(neighbor_count + 1, peak_times.size - index)):
            interval_seconds = float(peak_times[index + offset] - peak_time)
            if interval_seconds <= 0:
                continue
            theoretical_tempo = 60.0 / interval_seconds
            while theoretical_tempo < bpm_min:
                theoretical_tempo *= 2.0
            while theoretical_tempo > bpm_max:
                theoretical_tempo /= 2.0
            tempo_key = int(round(theoretical_tempo))
            tempo_counts[tempo_key] = tempo_counts.get(tempo_key, 0) + 1

    return tuple(
        TempoCandidate(tempo_bpm=tempo_bpm, count=count)
        for tempo_bpm, count in sorted(
            tempo_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )


def _as_mono_array(samples: Sequence[float] | np.ndarray) -> np.ndarray:
    array = np.asarray(samples, dtype=np.float32)
    if array.ndim == 1:
        return array
    if array.ndim == 2:
        return np.mean(array, axis=1, dtype=np.float32)
    msg = "samples must be one-dimensional mono or two-dimensional channel-major audio"
    raise ValueError(msg)


def _median_absolute_deviation(values: np.ndarray, window_size: int) -> np.ndarray:
    baseline = ndimage.median_filter(values, size=window_size, mode="nearest")
    deviation = ndimage.median_filter(
        np.abs(values - baseline),
        size=window_size,
        mode="nearest",
    )
    return baseline + deviation


def _causal_rolling_mean_std(
    values: np.ndarray,
    window_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return mean/std using only samples before the current frame."""

    if values.size == 0:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    cumsum = np.cumsum(np.concatenate(([0.0], values)))
    cumsum_sq = np.cumsum(np.concatenate(([0.0], np.square(values))))
    index = np.arange(values.size, dtype=np.int64)
    starts = np.maximum(0, index - window_size)
    counts = index - starts

    means = np.empty(values.size, dtype=np.float64)
    stds = np.empty(values.size, dtype=np.float64)

    valid = counts > 0
    means[~valid] = values[0]
    stds[~valid] = 0.0

    if np.any(valid):
        sums = cumsum[index[valid]] - cumsum[starts[valid]]
        sums_sq = cumsum_sq[index[valid]] - cumsum_sq[starts[valid]]
        mean_valid = sums / counts[valid]
        variance_valid = np.maximum((sums_sq / counts[valid]) - np.square(mean_valid), 0.0)
        means[valid] = mean_valid
        stds[valid] = np.sqrt(variance_valid)

    return means, stds


def _suppress_nearby_peaks(
    peaks: np.ndarray,
    strengths: np.ndarray,
    suppression_window_frames: int,
) -> np.ndarray:
    """Keep only the strongest peak inside each local neighborhood."""

    if peaks.size <= 1:
        return peaks

    order = np.argsort(strengths)[::-1]
    keep_mask = np.ones(peaks.size, dtype=bool)

    for ranked_index in order:
        if not keep_mask[ranked_index]:
            continue
        center = peaks[ranked_index]
        nearby = np.abs(peaks - center) <= suppression_window_frames
        nearby[ranked_index] = False
        keep_mask &= ~nearby
        keep_mask[ranked_index] = True

    return np.sort(peaks[keep_mask])


def _pick_recent_average_threshold_peaks(
    band_energy: np.ndarray,
    bootstrap_threshold: np.ndarray,
    *,
    threshold_scale: float,
    prominence: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Accept peaks above a threshold derived from the last few accepted peaks.

    Before any peaks have been accepted, a causal bootstrap threshold is used.
    Once peaks are accepted, the live threshold becomes:
        threshold_scale * average(last DEFAULT_RECENT_PEAK_COUNT accepted peaks)
    """

    candidate_peaks, _ = signal.find_peaks(
        band_energy,
        distance=1,
        prominence=prominence,
    )
    threshold = bootstrap_threshold.copy()
    if candidate_peaks.size == 0:
        return candidate_peaks, threshold

    accepted: list[int] = []
    recent_peak_values: deque[float] = deque(maxlen=DEFAULT_RECENT_PEAK_COUNT)
    active_threshold: float | None = None
    segment_start = 0

    for peak in candidate_peaks:
        threshold_at_peak = (
            active_threshold
            if active_threshold is not None
            else float(bootstrap_threshold[peak])
        )
        if active_threshold is not None:
            threshold[segment_start : peak + 1] = active_threshold

        peak_value = float(band_energy[peak])
        if peak_value < threshold_at_peak:
            continue

        accepted.append(int(peak))
        recent_peak_values.append(peak_value)
        active_threshold = max(
            threshold_scale * (sum(recent_peak_values) / len(recent_peak_values)),
            prominence,
            1e-6,
        )
        segment_start = peak + 1

    if active_threshold is not None:
        threshold[segment_start:] = active_threshold

    return np.asarray(accepted, dtype=np.int64), threshold


def analyze_transients(
    samples: Sequence[float] | np.ndarray,
    sample_rate: int,
    *,
    frame_size: int = DEFAULT_FRAME_SIZE,
    hop_size: int = DEFAULT_HOP_SIZE,
    threshold_window_seconds: float = DEFAULT_THRESHOLD_WINDOW_SECONDS,
    threshold_scale: float = DEFAULT_THRESHOLD_SCALE,
    min_spacing_ms: float = DEFAULT_MIN_SPACING_MS,
) -> TransientAnalysis:
    """Return an inspectable transient pass for a chunk of audio.

    The detector is intentionally simple and tunable:
    - short-time Fourier transform
    - low-band energy peaks
    - threshold from 2/3 of the average of the last 3 accepted peaks
    - peak picking with a refractory period
    """

    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if frame_size <= 0:
        raise ValueError("frame_size must be positive")
    if hop_size <= 0:
        raise ValueError("hop_size must be positive")

    mono = _as_mono_array(samples)
    duration_seconds = mono.size / float(sample_rate)

    if mono.size == 0:
        return TransientAnalysis(
            sample_rate=sample_rate,
            frame_size=frame_size,
            hop_size=hop_size,
            duration_seconds=0.0,
            band_low_hz=0.0,
            band_high_hz=0.0,
            estimated_bpm=None,
            bpm_consistency=0.0,
            frame_times=np.array([], dtype=np.float64),
            low_band_energy=np.array([], dtype=np.float64),
            raw_flux=np.array([], dtype=np.float64),
            onset_envelope=np.array([], dtype=np.float64),
            threshold=np.array([], dtype=np.float64),
            transients=(),
        )

    nperseg = min(frame_size, mono.size)
    noverlap = max(0, nperseg - hop_size)
    freqs, times, spectrum = signal.stft(
        mono,
        fs=sample_rate,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        nfft=max(frame_size, nperseg),
        boundary=None,
        padded=False,
    )

    if spectrum.shape[1] < 2:
        return TransientAnalysis(
            sample_rate=sample_rate,
            frame_size=frame_size,
            hop_size=hop_size,
            duration_seconds=duration_seconds,
            band_low_hz=0.0,
            band_high_hz=0.0,
            estimated_bpm=None,
            bpm_consistency=0.0,
            frame_times=np.array([], dtype=np.float64),
            low_band_energy=np.array([], dtype=np.float64),
            raw_flux=np.array([], dtype=np.float64),
            onset_envelope=np.array([], dtype=np.float64),
            threshold=np.array([], dtype=np.float64),
            transients=(),
        )

    magnitudes = np.abs(spectrum).astype(np.float64, copy=False)
    compressed = np.log1p(magnitudes * 25.0)

    positive_flux = np.maximum(0.0, np.diff(compressed, axis=1))
    high_band_mask = (freqs >= 2_000.0) & (freqs < 8_000.0)
    frame_times = times[1:].astype(np.float64, copy=False)
    feature_spectra = magnitudes[:, 1:]

    window_frames = max(
        3,
        int(round((threshold_window_seconds * sample_rate) / hop_size)),
    )
    if window_frames % 2 == 0:
        window_frames += 1

    min_distance_frames = max(
        1,
        int(round((min_spacing_ms / 1_000.0) * sample_rate / hop_size)),
    )
    best_summary: BandSummary | None = None
    best_low_hz = 0.0
    best_high_hz = 0.0
    best_energy = np.array([], dtype=np.float64)
    best_raw_flux = np.array([], dtype=np.float64)
    best_envelope = np.array([], dtype=np.float64)
    best_threshold = np.array([], dtype=np.float64)
    best_transients: tuple[Transient, ...] = ()

    for low_hz, high_hz in _build_frequency_ranges():
        band_mask = (freqs >= low_hz) & (freqs < high_hz)
        if not np.any(band_mask):
            continue

        raw_flux = np.sum(positive_flux[band_mask], axis=0)
        raw_flux = ndimage.gaussian_filter1d(raw_flux, sigma=1.0)

        band_energy = np.log1p(np.sum(np.square(magnitudes[band_mask, 1:]), axis=0))
        band_energy = ndimage.gaussian_filter1d(band_energy, sigma=1.0)

        energy_mean, energy_std = _causal_rolling_mean_std(band_energy, window_frames)
        energy_std = np.maximum(energy_std, 1e-6)
        energy_floor = max(float(np.percentile(band_energy, 10)), 1e-3)
        bootstrap_threshold = np.maximum(energy_mean + (0.5 * energy_std), energy_floor)
        prominence = max(float(np.percentile(band_energy, 75)) * 0.10, 1e-6)
        peaks, threshold = _pick_recent_average_threshold_peaks(
            band_energy,
            bootstrap_threshold,
            threshold_scale=threshold_scale,
            prominence=prominence,
        )
        onset_envelope = np.divide(
            band_energy,
            np.maximum(threshold, 1e-6),
        )
        suppression_window_frames = max(
            min_distance_frames,
            int(round((DEFAULT_SUPPRESSION_WINDOW_SECONDS * sample_rate) / hop_size)),
        )
        if peaks.size:
            peaks = _suppress_nearby_peaks(
                peaks,
                band_energy[peaks],
                suppression_window_frames,
            )

        transients: list[Transient] = []
        for peak in peaks:
            spectral_slice = feature_spectra[:, peak]
            total_energy = float(np.sum(spectral_slice)) + _EPSILON
            centroid = float(np.sum(freqs * spectral_slice) / total_energy)
            low_band_share = float(np.sum(spectral_slice[band_mask]) / total_energy)
            high_band_share = float(np.sum(spectral_slice[high_band_mask]) / total_energy)
            flatness = math.exp(float(np.mean(np.log(spectral_slice + _EPSILON)))) / (
                float(np.mean(spectral_slice + _EPSILON))
            )

            transients.append(
                Transient(
                    frame_index=int(peak),
                    time_seconds=float(frame_times[peak]),
                    strength=float(onset_envelope[peak]),
                    low_band_share=low_band_share,
                    high_band_share=high_band_share,
                    centroid_hz=centroid,
                    flatness=float(flatness),
                )
            )

        peak_times = frame_times[peaks] if peaks.size else np.array([], dtype=np.float64)
        tempo_candidates = _group_neighbors_by_tempo(peak_times)
        estimated_bpm: float | None = None
        bpm_consistency = 0.0
        score = 0.0
        if tempo_candidates:
            top_candidate = tempo_candidates[0]
            total_votes = sum(candidate.count for candidate in tempo_candidates)
            estimated_bpm = float(top_candidate.tempo_bpm)
            bpm_consistency = top_candidate.count / max(total_votes, 1)
            score = bpm_consistency * math.log1p(top_candidate.count)

        summary = BandSummary(
            low_hz=low_hz,
            high_hz=high_hz,
            transient_count=len(transients),
            estimated_bpm=estimated_bpm,
            bpm_consistency=bpm_consistency,
            score=score,
            tempo_candidates=tempo_candidates[:5],
        )
        if best_summary is None or summary.score > best_summary.score:
            best_summary = summary
            best_low_hz = low_hz
            best_high_hz = high_hz
            best_energy = band_energy
            best_raw_flux = raw_flux
            best_envelope = onset_envelope
            best_threshold = threshold
            best_transients = tuple(transients)

    if best_summary is None:
        return TransientAnalysis(
            sample_rate=sample_rate,
            frame_size=frame_size,
            hop_size=hop_size,
            duration_seconds=duration_seconds,
            band_low_hz=0.0,
            band_high_hz=0.0,
            estimated_bpm=None,
            bpm_consistency=0.0,
            frame_times=frame_times,
            low_band_energy=np.array([], dtype=np.float64),
            raw_flux=np.array([], dtype=np.float64),
            onset_envelope=np.array([], dtype=np.float64),
            threshold=np.array([], dtype=np.float64),
            transients=(),
        )

    return TransientAnalysis(
        sample_rate=sample_rate,
        frame_size=frame_size,
        hop_size=hop_size,
        duration_seconds=duration_seconds,
        band_low_hz=best_low_hz,
        band_high_hz=best_high_hz,
        estimated_bpm=best_summary.estimated_bpm,
        bpm_consistency=best_summary.bpm_consistency,
        frame_times=frame_times,
        low_band_energy=best_energy,
        raw_flux=best_raw_flux,
        onset_envelope=best_envelope,
        threshold=best_threshold,
        transients=best_transients,
    )
