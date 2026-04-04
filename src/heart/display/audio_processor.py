"""Shared audio processing for beat detection.

This module contains the core onset detection and beat tracking logic,
shared between renderers and debug tools.
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Onset:
    """Represents a detected onset."""

    time: float  # Audio time in seconds
    is_main: bool = False  # Part of main beat sequence
    flux: float = 0.0  # Spectral flux at detection
    bass_energy: float = 0.0  # Bass energy at detection


@dataclass
class BeatState:
    """Current beat tracking state."""

    interval: float | None = None  # Seconds between beats (tempo)
    phase: float = 0.0  # Time of last confirmed beat
    is_locked: bool = False  # Whether we have a stable beat


@dataclass
class RejectedOnset:
    """An onset that was detected but rejected."""

    time: float  # Audio time
    reason: str  # Why it was rejected
    flux: float = 0.0
    low_mid_ratio: float = 0.0  # E_low / E_mid
    high_low_ratio: float = 0.0  # E_high / E_low


@dataclass
class AudioProcessorState:
    """Full state of the audio processor."""

    # Audio buffers
    audio_blocks: list[np.ndarray] = field(default_factory=list)
    block_times: list[float] = field(default_factory=list)

    # Spectrum data for visualization
    spectrums: list[np.ndarray] = field(default_factory=list)
    bass_energies: list[float] = field(default_factory=list)
    flux_values: list[float] = field(default_factory=list)
    thresholds: list[float] = field(default_factory=list)

    # Onsets
    onsets: list[Onset] = field(default_factory=list)
    rejected_onsets: list[RejectedOnset] = field(default_factory=list)

    # Beat tracking
    beat: BeatState = field(default_factory=BeatState)


class AudioProcessor:
    """Core audio processing for beat detection."""

    # Audio settings
    SAMPLERATE = 44100
    BLOCK_SIZE = 1024

    # Frequency bands for kick detection
    BASS_LOW_HZ = 35
    BASS_HIGH_HZ = 140
    MID_LOW_HZ = 150
    MID_HIGH_HZ = 400
    HIGH_LOW_HZ = 2000
    HIGH_HIGH_HZ = 10000

    # BPM constraints
    MIN_BPM = 80
    MAX_BPM = 250

    def __init__(self, sensitivity: float = 1.0) -> None:
        """Initialize the audio processor.

        Args:
            sensitivity: Beat detection sensitivity (higher = more sensitive).
        """
        self._sensitivity = sensitivity
        self._min_interval = 60.0 / self.MAX_BPM

        # FFT state (initialized on first block)
        self._fft_freqs: np.ndarray | None = None
        self._bass_mask: np.ndarray | None = None
        self._mid_mask: np.ndarray | None = None
        self._high_mask: np.ndarray | None = None

        # Processing state
        self._bass_energy_history: list[float] = []
        self._flux_history: list[float] = []
        self._last_main_time: float = 0.0
        self._recording_start_time: float | None = None

        # Output state
        self.state = AudioProcessorState()

    def reset(self) -> None:
        """Reset all state."""
        self._bass_energy_history = []
        self._flux_history = []
        self._last_main_time = 0.0
        self._recording_start_time = None
        self.state = AudioProcessorState()

    def process_block(self, audio: np.ndarray, stream_time: float) -> Onset | None:
        """Process an audio block and detect onsets.

        Args:
            audio: Audio samples (mono, float32)
            stream_time: Timestamp from audio stream

        Returns:
            Onset if detected, None otherwise
        """
        # Track recording start time
        if self._recording_start_time is None:
            self._recording_start_time = stream_time

        # Convert to relative time
        audio_time = stream_time - self._recording_start_time

        # Store audio block
        self.state.audio_blocks.append(audio.copy())
        self.state.block_times.append(audio_time)

        # Initialize FFT bins and frequency band masks
        if self._fft_freqs is None:
            self._fft_freqs = np.fft.rfftfreq(len(audio), 1.0 / self.SAMPLERATE)
            self._bass_mask = (self._fft_freqs >= self.BASS_LOW_HZ) & (
                self._fft_freqs <= self.BASS_HIGH_HZ
            )
            self._mid_mask = (self._fft_freqs >= self.MID_LOW_HZ) & (
                self._fft_freqs <= self.MID_HIGH_HZ
            )
            self._high_mask = (self._fft_freqs >= self.HIGH_LOW_HZ) & (
                self._fft_freqs <= self.HIGH_HIGH_HZ
            )

        # Compute spectrum
        windowed = audio * np.hanning(len(audio))
        spectrum = np.abs(np.fft.rfft(windowed))
        self.state.spectrums.append(spectrum)

        # Compute bass energy
        E_low = float(np.sum(spectrum[self._bass_mask] ** 2))
        E_mid = float(np.sum(spectrum[self._mid_mask] ** 2))
        E_high = float(np.sum(spectrum[self._high_mask] ** 2))
        self.state.bass_energies.append(E_low)

        # Track energy for adaptive threshold
        self._bass_energy_history.append(E_low)
        if len(self._bass_energy_history) > 50:
            self._bass_energy_history.pop(0)

        # Check for beat loss
        if self.state.beat.interval is not None:
            time_since_phase = audio_time - self.state.beat.phase
            beats_elapsed = time_since_phase / self.state.beat.interval
            if beats_elapsed > 3:
                # Beat lost
                self.state.beat.interval = None
                self.state.beat.phase = 0.0
                self.state.beat.is_locked = False

        # Need at least 2 blocks for flux
        if len(self._bass_energy_history) < 2:
            self.state.flux_values.append(0.0)
            self.state.thresholds.append(0.0)
            return None

        # Compute log-energy spectral flux (more perceptually relevant)
        # Log-energy reduces sensitivity to loud sustained sounds while
        # preserving transient detection
        eps = 1e-9
        prev_energy = self._bass_energy_history[-2]
        bass_log = np.log(E_low + eps)
        prev_bass_log = np.log(prev_energy + eps)
        flux = max(0.0, float(bass_log - prev_bass_log))
        self.state.flux_values.append(flux)

        # Track flux for threshold - 20 second history (~860 blocks at 44100/1024)
        self._flux_history.append(flux)
        if len(self._flux_history) > 860:
            self._flux_history.pop(0)

        if len(self._flux_history) < 20:
            self.state.thresholds.append(0.0)
            return None

        # Percentile-based threshold: only detect if flux is in top 10%
        # This ensures we only catch the strongest transients (kicks)
        # regardless of overall volume level
        percentile = (
            90.0 - (self._sensitivity - 1.0) * 10
        )  # sensitivity 1.0 = 90th, 2.0 = 80th
        percentile = max(70.0, min(99.0, percentile))  # Clamp to reasonable range
        threshold = np.percentile(self._flux_history, percentile)
        self.state.thresholds.append(threshold)

        # Check for onset - must be in top percentile of flux values
        if flux <= threshold:
            return None

        # Compute band ratios for kick detection
        low_mid_ratio = E_low / (E_mid + eps)
        high_low_ratio = E_high / (E_low + eps)

        # Get precise time for rejection tracking
        precise_time = self._find_precise_onset(audio, audio_time)

        # Band-ratio gates for kick detection
        # Instead of comparing bass to full spectrum (which includes reverb/pads),
        # we compare specific bands to identify kick-like spectral shape

        # Gate 1: Low must dominate mid (kicks have steep rolloff after ~150 Hz)
        # Snares/claps have more mid-frequency content
        if low_mid_ratio < 2.0:
            self.state.rejected_onsets.append(
                RejectedOnset(
                    time=precise_time,
                    reason=f"low/mid={low_mid_ratio:.1f}<2",
                    flux=flux,
                    low_mid_ratio=low_mid_ratio,
                    high_low_ratio=high_low_ratio,
                )
            )
            # Keep only last 100 rejections
            if len(self.state.rejected_onsets) > 100:
                self.state.rejected_onsets.pop(0)
            return None

        # Gate 2: High-frequency penalty (reject bright hits like hi-hats/claps)
        # Kicks can co-occur with hats, so this is a penalty not a hard veto
        # A ratio > 0.4 means too much high-freq energy relative to the kick
        if high_low_ratio > 0.4:
            self.state.rejected_onsets.append(
                RejectedOnset(
                    time=precise_time,
                    reason=f"high/low={high_low_ratio:.2f}>0.4",
                    flux=flux,
                    low_mid_ratio=low_mid_ratio,
                    high_low_ratio=high_low_ratio,
                )
            )
            # Keep only last 100 rejections
            if len(self.state.rejected_onsets) > 100:
                self.state.rejected_onsets.pop(0)
            return None

        # Check if this matches beat pattern
        is_main = False
        time_since_main = precise_time - self._last_main_time

        if self.state.beat.interval is not None:
            time_since_phase = precise_time - self.state.beat.phase
            beats_elapsed = time_since_phase / self.state.beat.interval
            phase_error = abs(beats_elapsed - round(beats_elapsed))

            # On beat if timing within 15% AND enough time since last main
            if phase_error < 0.15 and time_since_main > self.state.beat.interval * 0.5:
                is_main = True
                self.state.beat.phase = precise_time
                self._last_main_time = precise_time

        # Create onset
        onset = Onset(
            time=precise_time,
            is_main=is_main,
            flux=flux,
            bass_energy=E_low,
        )
        self.state.onsets.append(onset)

        # Only update for MAIN beats
        if is_main:
            self._last_main_time = precise_time

        # Beat sequence detection - runs even when we have a beat
        # Override current beat if we find a longer/better sequence
        if len(self.state.onsets) >= 4:
            interval, sequence = self._find_beat_sequence(precise_time)
            if interval and len(sequence) >= 3:
                # Count how many recent onsets match current beat vs new sequence
                current_matches = 0
                if self.state.beat.interval is not None:
                    for o in self.state.onsets[-20:]:  # Check last 20 onsets
                        if o.is_main:
                            current_matches += 1

                # Override if: no beat yet, OR new sequence is longer
                should_override = (
                    self.state.beat.interval is None
                    or len(sequence) > current_matches + 2
                )

                if should_override:
                    self.state.beat.interval = interval
                    self.state.beat.phase = self.state.onsets[sequence[-1]].time
                    self.state.beat.is_locked = True

                    # Mark sequence onsets as main
                    for idx in sequence:
                        self.state.onsets[idx].is_main = True
                        self._last_main_time = self.state.onsets[idx].time

                    # Mark current if in sequence
                    if len(self.state.onsets) - 1 in sequence:
                        onset.is_main = True

        return onset

    def _find_precise_onset(self, audio: np.ndarray, block_time: float) -> float:
        """Find precise onset time within a block.

        Uses envelope threshold crossing rather than max amplitude, which
        better identifies the attack onset rather than a later oscillation peak.
        """
        abs_audio = np.abs(audio)

        # Create a simple lowpass envelope via moving average
        # 32 samples at 44100 Hz ≈ 0.7ms smoothing window
        kernel_size = 32
        kernel = np.ones(kernel_size) / kernel_size
        envelope = np.convolve(abs_audio, kernel, mode="same")

        # Find first crossing of 30% of peak envelope
        # This catches the attack rather than a later peak
        threshold = np.max(envelope) * 0.3
        crossings = np.where(envelope > threshold)[0]

        if len(crossings) > 0:
            first_cross = crossings[0]
            offset = first_cross / self.SAMPLERATE
            return block_time + offset

        # Fallback to start of block if no crossing found
        return block_time

    def _find_beat_sequence(
        self, current_time: float
    ) -> tuple[float | None, list[int]]:
        """Find consistent beat sequence from onsets."""
        onset_times = [o.time for o in self.state.onsets]
        n = len(onset_times)
        if n < 3:
            return None, []

        best_sequence: list[int] = []
        best_interval: float | None = None

        for j in range(n - 1, 0, -1):
            i = j - 1
            interval = onset_times[j] - onset_times[i]

            # Skip if outside BPM range
            if not (self._min_interval <= interval <= 60.0 / self.MIN_BPM):
                continue

            # Build sequence backwards
            sequence = [i, j]
            expected_time = onset_times[i] - interval

            for k in range(i - 1, -1, -1):
                time_error = abs(onset_times[k] - expected_time)
                if time_error < interval * 0.2:
                    sequence.insert(0, k)
                    expected_time = onset_times[k] - interval
                elif onset_times[k] < expected_time - interval * 0.5:
                    break

            # Reject stale sequences
            if sequence:
                last_beat_time = onset_times[sequence[-1]]
                beats_late = (current_time - last_beat_time) / interval
                if beats_late > 3:
                    continue

            if len(sequence) >= 3 and len(sequence) > len(best_sequence):
                best_sequence = sequence
                best_interval = interval

        # Tempo octave correction: prefer double-time (faster) if onsets exist
        # This ensures we catch every kick rather than every other kick
        if best_interval is not None and len(best_sequence) >= 3:
            halved_interval = best_interval / 2
            # Only consider if halved interval is still in valid BPM range
            if halved_interval >= self._min_interval:
                # Check if there are onsets at the half-interval positions
                # (i.e., between existing beats)
                halved_matches = 0
                phase = onset_times[best_sequence[-1]]
                for idx in range(len(self.state.onsets)):
                    t = onset_times[idx]
                    # Check if this onset is on a half-beat
                    beats_from_phase = (t - phase) / halved_interval
                    error = abs(beats_from_phase - round(beats_from_phase))
                    if error < 0.1:  # Within 20% of expected beat time
                        halved_matches += 1

                # If we find significantly more matches at double-time, use it
                if halved_matches >= len(best_sequence) * 1.8:
                    best_interval = halved_interval

        return best_interval, best_sequence

    @property
    def current_time(self) -> float:
        """Get current audio time."""
        if self.state.block_times:
            return self.state.block_times[-1]
        return 0.0

    @property
    def bpm(self) -> float | None:
        """Get current BPM if beat is locked."""
        if self.state.beat.interval:
            return 60.0 / self.state.beat.interval
        return None
