from __future__ import annotations

import math

import numpy as np

from heart.utilities.transients import analyze_transients


class TestUtilitiesTransients:
    """Keep the exploratory transient detector predictable on synthetic audio."""

    def test_detects_kick_like_pulses(self) -> None:
        sample_rate = 22_050
        duration_seconds = 2.0
        samples = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)

        pulse_times = (0.5, 1.0, 1.5)
        pulse_length = int(sample_rate * 0.08)
        t = np.arange(pulse_length, dtype=np.float32) / float(sample_rate)
        envelope = np.exp(-35.0 * t)
        pulse = 0.9 * envelope * np.sin(2.0 * math.pi * 70.0 * t)

        for onset_time in pulse_times:
            start = int(onset_time * sample_rate)
            end = min(start + pulse_length, samples.size)
            samples[start:end] += pulse[: end - start]

        analysis = analyze_transients(
            samples,
            sample_rate=sample_rate,
            frame_size=1024,
            hop_size=256,
            min_spacing_ms=120.0,
        )

        detected_times = np.array(
            [transient.time_seconds for transient in analysis.transients],
            dtype=np.float64,
        )

        assert detected_times.size >= 3
        assert analysis.estimated_bpm == 120.0
        for pulse_time in pulse_times:
            assert np.any(np.abs(detected_times - pulse_time) <= 0.06)

    def test_preserves_kick_pulses_even_with_bright_hats_present(self) -> None:
        sample_rate = 22_050
        duration_seconds = 4.0
        samples = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)

        kick_times = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5)
        kick_length = int(sample_rate * 0.08)
        kick_t = np.arange(kick_length, dtype=np.float32) / float(sample_rate)
        kick = (
            0.95
            * np.exp(-30.0 * kick_t)
            * np.sin(2.0 * math.pi * 75.0 * kick_t)
        )

        hat_times = tuple(np.arange(0.25, 3.76, 0.25))
        hat_length = int(sample_rate * 0.03)
        hat_t = np.arange(hat_length, dtype=np.float32) / float(sample_rate)
        hat = (
            0.55
            * np.exp(-120.0 * hat_t)
            * np.sin(2.0 * math.pi * 4_000.0 * hat_t)
        )

        for onset_time in kick_times:
            start = int(onset_time * sample_rate)
            end = min(start + kick_length, samples.size)
            samples[start:end] += kick[: end - start]

        for onset_time in hat_times:
            start = int(onset_time * sample_rate)
            end = min(start + hat_length, samples.size)
            samples[start:end] += hat[: end - start]

        analysis = analyze_transients(
            samples,
            sample_rate=sample_rate,
            frame_size=1024,
            hop_size=256,
            min_spacing_ms=100.0,
        )

        detected_times = np.array(
            [transient.time_seconds for transient in analysis.transients],
            dtype=np.float64,
        )

        assert detected_times.size >= 5
        assert analysis.estimated_bpm == 120.0
        for kick_time in kick_times[2:]:
            assert np.any(np.abs(detected_times - kick_time) <= 0.07)
        assert detected_times.size <= len(hat_times) + len(kick_times) + 2

    def test_detects_large_low_band_pulses_with_slower_attack(self) -> None:
        sample_rate = 22_050
        duration_seconds = 2.2
        samples = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)

        pulse_times = (0.5, 1.0, 1.5)
        pulse_length = int(sample_rate * 0.14)
        attack_length = int(sample_rate * 0.02)
        t = np.arange(pulse_length, dtype=np.float32) / float(sample_rate)
        attack = np.minimum(t / max(attack_length / sample_rate, 1e-6), 1.0)
        decay = np.exp(-18.0 * t)
        pulse = 1.1 * attack * decay * np.sin(2.0 * math.pi * 68.0 * t)

        for onset_time in pulse_times:
            start = int(onset_time * sample_rate)
            end = min(start + pulse_length, samples.size)
            samples[start:end] += pulse[: end - start]

        analysis = analyze_transients(
            samples,
            sample_rate=sample_rate,
            frame_size=1024,
            hop_size=256,
            min_spacing_ms=120.0,
        )

        detected_times = np.array(
            [transient.time_seconds for transient in analysis.transients],
            dtype=np.float64,
        )

        assert detected_times.size >= 3
        assert analysis.estimated_bpm == 120.0
        for pulse_time in pulse_times:
            assert np.any(np.abs(detected_times - pulse_time) <= 0.08)

    def test_suppresses_small_spikes_around_large_spike(self) -> None:
        sample_rate = 22_050
        duration_seconds = 2.0
        samples = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)

        cluster_times = (0.50, 0.60, 0.69)
        next_main_time = 1.00
        pulse_length = int(sample_rate * 0.08)
        t = np.arange(pulse_length, dtype=np.float32) / float(sample_rate)

        main_pulse = 1.0 * np.exp(-28.0 * t) * np.sin(2.0 * math.pi * 70.0 * t)
        small_pulse = 0.28 * np.exp(-30.0 * t) * np.sin(2.0 * math.pi * 70.0 * t)

        for onset_time in cluster_times:
            start = int(onset_time * sample_rate)
            end = min(start + pulse_length, samples.size)
            pulse = main_pulse if onset_time == cluster_times[0] else small_pulse
            samples[start:end] += pulse[: end - start]

        start = int(next_main_time * sample_rate)
        end = min(start + pulse_length, samples.size)
        samples[start:end] += main_pulse[: end - start]

        analysis = analyze_transients(
            samples,
            sample_rate=sample_rate,
            frame_size=1024,
            hop_size=256,
            min_spacing_ms=100.0,
        )

        detected_times = np.array(
            [transient.time_seconds for transient in analysis.transients],
            dtype=np.float64,
        )

        cluster_hits = detected_times[np.abs(detected_times - 0.50) <= 0.20]
        assert cluster_hits.size == 1
        assert np.any(np.abs(detected_times - 0.50) <= 0.07)
        assert np.any(np.abs(detected_times - 1.00) <= 0.07)
