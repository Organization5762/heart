"""Beat-reactive renderer that detects onsets and records a click track.

Simplified to just:
1. Detect bass onsets
2. Record audio + click track for visualization in Audacity
"""

import atexit
import os
import time as _time
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pygame
from PIL import Image, ImageDraw

from heart.device import Orientation
from heart.display.beat_state import update_beat_state
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

# Track active instances for cleanup on exit
_active_instances: list["BeatFlashRenderer"] = []


def _cleanup_on_exit() -> None:
    """Save recordings when program exits."""
    logger.info(f"Cleanup: {len(_active_instances)} active instances")
    for instance in _active_instances[:]:  # Copy list since stop() modifies it
        logger.info(
            f"Stopping instance with {len(instance._recorded_audio)} audio blocks"
        )
        instance.stop()


atexit.register(_cleanup_on_exit)

sd: Any | None = None
try:
    import sounddevice as _sounddevice

    sd = cast(Any, _sounddevice)
except Exception:
    sd = None


@dataclass
class BeatFlashState:
    """State for the beat flash renderer."""

    is_listening: bool = False


class BeatFlashRenderer(AtomicBaseRenderer[BeatFlashState]):
    """Renderer that detects onsets and saves a click track."""

    # Audio settings
    SAMPLERATE = 44100
    BLOCK_SIZE = 1024
    CHANNELS = 1

    # Bass detection
    BASS_LOW_HZ = 30
    BASS_HIGH_HZ = 150

    # BPM constraints
    MIN_BPM = 80
    MAX_BPM = 250

    def __init__(
        self,
        *,
        sensitivity: float = 1.0,
        device: int | str | None = None,
        output_file: str = "~/Desktop/onset_clicks.wav",
        render_flash: bool = True,
    ) -> None:
        """Initialize the onset detector.

        Args:
            sensitivity: Beat detection sensitivity (higher = more sensitive).
            device: Audio input device. Use 'loopback' to auto-detect.
            output_file: Path to save the click track WAV file.
            render_flash: Whether to render blue flash on beat (False for headless detection).
        """
        self._sensitivity = sensitivity
        self._device = device
        self._output_file = os.path.expanduser(output_file)
        self._render_flash = render_flash
        self._stream: Any | None = None

        # Timing
        self._stream_start_wall_time: float = 0.0
        self._recording_start_time: float | None = None  # First audio block time
        self._block_duration: float = self.BLOCK_SIZE / self.SAMPLERATE
        self._min_interval = 60.0 / self.MAX_BPM

        # Onset detection state
        self._bass_energy_history: list[float] = []
        self._last_onset_time: float = 0.0
        self._recording_start_wall_time: float = 0.0  # Wall time when recording started

        # Recording buffers
        self._recorded_audio: list[np.ndarray] = []
        self._onset_times: list[float] = []  # Times relative to recording start
        self._onset_is_main_beat: list[bool] = []  # True if part of main beat sequence

        # Beat tracking
        self._beat_interval: float | None = (
            None  # Detected tempo (seconds between beats)
        )
        self._beat_phase: float = 0.0  # Time of last confirmed beat
        self._consecutive_missed_beats: int = 0  # Count of missed beats in a row

        # FFT state
        self._fft_freqs: np.ndarray | None = None
        self._bass_mask: np.ndarray | None = None

        super().__init__()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> BeatFlashState:
        """Create initial state and start audio capture."""
        state = BeatFlashState()

        # Register for cleanup on exit
        _active_instances.append(self)

        if sd is not None:
            try:
                self._start_audio_stream()
                state = BeatFlashState(is_listening=True)
                logger.info(
                    f"Recording audio, will save clicks to: {self._output_file}"
                )
            except Exception as e:
                logger.warning(f"Failed to start audio: {e}")
        else:
            logger.warning("sounddevice not available")

        return state

    def _resolve_device(self) -> int | str | None:
        """Resolve the device parameter, auto-detecting loopback if requested."""
        if self._device != "loopback":
            return self._device

        if sd is None:
            return None

        devices = sd.query_devices()
        loopback_names = ["blackhole", "loopback", "soundflower"]
        for i, dev in enumerate(devices):
            name = dev.get("name", "").lower()
            if dev.get("max_input_channels", 0) > 0:
                if any(lb in name for lb in loopback_names):
                    logger.info(f"Auto-detected loopback device: {dev['name']}")
                    return i
        logger.warning("No loopback device found, using default input")
        return None

    def _start_audio_stream(self) -> None:
        """Start the audio input stream."""
        if sd is None:
            return

        device = self._resolve_device()
        logger.info(f"Using audio input device: {device}")

        self._stream = sd.InputStream(
            device=device,
            samplerate=self.SAMPLERATE,
            channels=self.CHANNELS,
            blocksize=self.BLOCK_SIZE,
            callback=self._audio_callback,
        )
        self._stream_start_wall_time = _time.time()
        self._stream.start()

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info: Any, status: Any
    ) -> None:
        """Detect bass onsets and record audio."""
        if status:
            logger.debug(f"Audio status: {status}")

        audio = np.asarray(indata).flatten().astype(np.float32)
        if audio.size == 0:
            return

        # Record the audio
        self._recorded_audio.append(audio.copy())

        # Calculate audio timestamp (relative to recording start)

        stream_time = time_info.inputBufferAdcTime

        # Track recording start time
        if self._recording_start_time is None:
            self._recording_start_time = stream_time
            self._recording_start_wall_time = _time.time()

        # Convert to relative time (0 = start of recording)
        audio_time = stream_time - self._recording_start_time

        # Initialize FFT bins
        if self._fft_freqs is None:
            self._fft_freqs = np.fft.rfftfreq(len(audio), 1.0 / self.SAMPLERATE)
            self._bass_mask = (self._fft_freqs >= self.BASS_LOW_HZ) & (
                self._fft_freqs <= self.BASS_HIGH_HZ
            )

        # Compute bass energy
        windowed = audio * np.hanning(len(audio))
        spectrum = np.abs(np.fft.rfft(windowed))
        bass_energy = float(np.sum(spectrum[self._bass_mask] ** 2))

        # Track energy for adaptive threshold
        self._bass_energy_history.append(bass_energy)
        if len(self._bass_energy_history) > 50:
            self._bass_energy_history.pop(0)

        # Detect onset using spectral flux (difference from previous frame)
        if len(self._bass_energy_history) >= 2:
            prev_energy = self._bass_energy_history[-2]

            # Spectral flux: how much did energy increase?
            flux = max(0, bass_energy - prev_energy)

            # Adaptive threshold based on recent flux values
            if not hasattr(self, "_flux_history"):
                self._flux_history: list[float] = []
                self._debug_counter = 0
            self._flux_history.append(flux)
            if len(self._flux_history) > 50:
                self._flux_history.pop(0)

            if len(self._flux_history) >= 5:
                mean_flux = np.mean(self._flux_history)
                std_flux = np.std(self._flux_history)
                # Lower threshold for more sensitivity
                threshold = mean_flux + std_flux * (1.0 / self._sensitivity)

                time_since_last = audio_time - self._last_onset_time

                if (
                    flux > threshold
                    and threshold > 0
                    and time_since_last > self._min_interval * 0.8
                ):
                    # Refine onset time by finding exact transient in the block
                    precise_time, _ = self._find_precise_onset_with_index(
                        audio, stream_time
                    )

                    # Check if this onset matches established beat pattern
                    is_main = False
                    phase_error = 0.0
                    if self._beat_interval is not None:
                        # Check if onset is near expected beat time
                        time_since_phase = precise_time - self._beat_phase
                        beats_elapsed = time_since_phase / self._beat_interval
                        phase_error = abs(beats_elapsed - round(beats_elapsed))

                        # On beat if timing within 15%
                        if phase_error < 0.15:
                            is_main = True
                            self._consecutive_missed_beats = 0
                            # Update phase to this onset for better tracking
                            self._beat_phase = precise_time
                            # Update shared beat state for other renderers
                            update_beat_state(
                                phase=self._audio_time_to_wall_time(precise_time),
                            )
                        else:
                            # Beat missed - stop sprite immediately
                            self._consecutive_missed_beats += 1
                            update_beat_state(clear_interval=True)

                            if self._consecutive_missed_beats >= 3:
                                # After 3 missed beats, fully reset beat tracking
                                print(
                                    f"*** BEAT LOST ({self._consecutive_missed_beats} "
                                    "consecutive misses) - searching for new beat ***"
                                )
                                self._beat_interval = None
                                self._beat_phase = 0.0
                                self._consecutive_missed_beats = 0

                    self._onset_times.append(precise_time)
                    self._onset_is_main_beat.append(is_main)
                    self._last_onset_time = precise_time

                    # Trim to keep only last 10 seconds of onset data
                    self._trim_onset_history(precise_time, max_age=10.0)

                    # Initial beat detection (before we have a locked beat)
                    if self._beat_interval is None and len(self._onset_times) >= 4:
                        interval, sequence = self._find_beat_sequence(precise_time)
                        if interval and len(sequence) >= 3:
                            self._beat_interval = interval
                            self._beat_phase = self._onset_times[sequence[-1]]

                            # Update shared beat state for other renderers
                            update_beat_state(
                                interval=interval,
                                phase=self._audio_time_to_wall_time(self._beat_phase),
                            )

                            # Mark all onsets in sequence as main beats
                            for idx in sequence:
                                self._onset_is_main_beat[idx] = True

                            # Also mark current if it's in the sequence
                            if len(self._onset_times) - 1 in sequence:
                                is_main = True
                                self._onset_is_main_beat[-1] = True

                    # Print status
                    bpm = 60.0 / self._beat_interval if self._beat_interval else 0
                    if self._beat_interval:
                        if is_main:
                            print(f"MAIN +{time_since_last:.3f}s | {bpm:.0f} BPM")
                        else:
                            print(
                                f"miss +{time_since_last:.3f}s (err={phase_error:.0%})"
                            )
                    else:
                        print(f"+{time_since_last:.3f}s")

    def _trim_onset_history(self, current_time: float, max_age: float = 10.0) -> None:
        """Trim onset history to keep only recent data.

        Args:
            current_time: Current audio time
            max_age: Maximum age in seconds to keep
        """
        cutoff_time = current_time - max_age
        # Find first index that's within the window
        trim_idx = 0
        for i, t in enumerate(self._onset_times):
            if t >= cutoff_time:
                trim_idx = i
                break
        else:
            # All onsets are too old
            trim_idx = len(self._onset_times)

        if trim_idx > 0:
            self._onset_times = self._onset_times[trim_idx:]
            self._onset_is_main_beat = self._onset_is_main_beat[trim_idx:]

    def _find_beat_sequence(
        self, current_time: float
    ) -> tuple[float | None, list[int]]:
        """Find the most consistent sequence of beats based on timing.

        Args:
            current_time: Current audio time, used to reject stale sequences

        Returns (interval, indices) where indices are the onsets forming the beat.
        """
        n = len(self._onset_times)
        if n < 3:
            return None, []

        times = self._onset_times

        best_sequence: list[int] = []
        best_interval: float | None = None

        # Try consecutive pairs, starting from the end (most recent)
        for j in range(n - 1, 0, -1):
            i = j - 1
            interval = times[j] - times[i]

            # Skip if interval outside BPM range
            if not (self._min_interval <= interval <= 60.0 / self.MIN_BPM):
                continue

            # Build sequence backwards
            sequence = [i, j]
            expected_time = times[i] - interval

            for k in range(i - 1, -1, -1):
                # Check if onset k is near expected time (within 20%)
                time_error = abs(times[k] - expected_time)
                if time_error < interval * 0.2:
                    sequence.insert(0, k)
                    expected_time = times[k] - interval
                elif times[k] < expected_time - interval * 0.5:
                    # Too far back, stop building
                    break

            # Reject if sequence's last beat is more than 3 beats late
            if sequence:
                last_beat_time = times[sequence[-1]]
                beats_late = (current_time - last_beat_time) / interval
                if beats_late > 3:
                    continue

            if len(sequence) >= 3 and len(sequence) > len(best_sequence):
                best_sequence = sequence
                best_interval = interval
                print(
                    f"    [SEQUENCE] len={len(sequence)}, "
                    f"interval={interval:.3f}s ({60/interval:.1f} BPM)"
                )

        return best_interval, best_sequence

    def _save_timeline_image(self) -> None:
        """Save a timeline image showing all onsets and their classification."""
        if not self._onset_times:
            return

        # Image dimensions
        width = 1200
        height = 200
        margin = 50
        timeline_y = height // 2

        # Create image
        img = Image.new("RGB", (width, height), (30, 30, 30))
        draw = ImageDraw.Draw(img)

        # Get time range
        max_time = max(self._onset_times) + 1.0
        min_time = 0.0
        time_range = max_time - min_time

        def time_to_x(t: float) -> int:
            return int(margin + (t - min_time) / time_range * (width - 2 * margin))

        # Draw timeline
        draw.line(
            [(margin, timeline_y), (width - margin, timeline_y)],
            fill=(100, 100, 100),
            width=2,
        )

        # Draw time markers every second
        for t in range(int(max_time) + 1):
            x = time_to_x(t)
            draw.line([(x, timeline_y - 10), (x, timeline_y + 10)], fill=(80, 80, 80))
            draw.text((x - 10, timeline_y + 15), f"{t}s", fill=(150, 150, 150))

        # Draw expected beat grid if we have a beat interval
        if self._beat_interval:
            t = self._beat_phase % self._beat_interval
            while t < max_time:
                x = time_to_x(t)
                draw.line(
                    [(x, timeline_y - 30), (x, timeline_y + 30)],
                    fill=(60, 60, 80),
                    width=1,
                )
                t += self._beat_interval

        # Draw onsets
        for i, onset_time in enumerate(self._onset_times):
            is_main = (
                self._onset_is_main_beat[i]
                if i < len(self._onset_is_main_beat)
                else False
            )
            x = time_to_x(onset_time)

            if is_main:
                # Main beat: tall blue line
                color = (50, 150, 255)
                draw.line(
                    [(x, timeline_y - 50), (x, timeline_y + 50)], fill=color, width=3
                )
                draw.ellipse(
                    [(x - 5, timeline_y - 5), (x + 5, timeline_y + 5)], fill=color
                )
            else:
                # Other: short red line
                color = (255, 100, 100)
                draw.line(
                    [(x, timeline_y - 25), (x, timeline_y + 25)], fill=color, width=2
                )
                draw.ellipse(
                    [(x - 3, timeline_y - 3), (x + 3, timeline_y + 3)], fill=color
                )

        # Draw legend and stats
        main_count = sum(self._onset_is_main_beat) if self._onset_is_main_beat else 0
        other_count = len(self._onset_times) - main_count
        bpm_str = (
            f"{60.0 / self._beat_interval:.1f} BPM"
            if self._beat_interval
            else "detecting..."
        )

        draw.text((margin, 10), f"Beat Timeline: {bpm_str}", fill=(255, 255, 255))
        draw.text(
            (margin, 30),
            f"Main: {main_count} (blue)  Other: {other_count} (red)",
            fill=(200, 200, 200),
        )

        # Save image
        output_path = os.path.expanduser("~/Desktop/beat_timeline.png")
        img.save(output_path)

    def _find_precise_onset_with_index(
        self, audio: np.ndarray, block_start_time: float
    ) -> tuple[float, int]:
        """Find precise onset time and sample index within the audio block.

        Uses threshold crossing: finds first sample where amplitude
        rises above 20% of the block's peak. This catches the transient attack.

        Args:
            audio: Raw audio samples from the current block
            block_start_time: Timestamp of block start (absolute stream time)

        Returns:
            (precise_time, sample_index) - time relative to recording start, and
            the sample index within the block where onset was detected
        """
        # Get absolute amplitude
        abs_audio = np.abs(audio)
        peak = np.max(abs_audio)

        if peak < 1e-6:  # Silence
            sample_offset = len(audio) // 2
            return (
                block_start_time
                + self._block_duration / 2
                - self._recording_start_time,
                sample_offset,
            )

        # Threshold: 20% of peak amplitude
        threshold = peak * 0.2

        # Find first sample exceeding threshold
        crossings = np.where(abs_audio > threshold)[0]

        if len(crossings) == 0:
            # Fallback to middle of block
            sample_offset = len(audio) // 2
        else:
            sample_offset = crossings[0]

        # Calculate precise time
        # Sample 0 is at block_start_time
        # At 44100 Hz, each sample is ~0.023ms, so we get sub-ms precision
        precise_time = block_start_time + (sample_offset / self.SAMPLERATE)

        # Convert to relative time
        return precise_time - self._recording_start_time, sample_offset

    def _audio_time_to_wall_time(self, audio_time: float) -> float:
        """Convert audio time (relative to recording start) to wall clock time."""
        return self._recording_start_wall_time + audio_time

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        """Flash blue for 50ms on each main beat."""
        now = _time.time()

        flash = False

        # Use established beat pattern for prediction
        if self._beat_interval is not None and self._beat_phase > 0:
            # Convert phase to wall time
            phase_wall = self._audio_time_to_wall_time(self._beat_phase)

            # Calculate time since last beat phase
            time_since_phase = now - phase_wall

            # How many beats have elapsed?
            beats_elapsed = time_since_phase / self._beat_interval

            # Phase within current beat (0.0 = on beat, 0.5 = off beat)
            phase = beats_elapsed % 1.0

            # Flash for 50ms around each beat (phase near 0 or 1)
            # 50ms / interval gives us the phase window
            phase_window = 0.05 / self._beat_interval  # 50ms window

            if phase < phase_window or phase > (1.0 - phase_window):
                flash = True

        if self._render_flash:
            if flash:
                window.fill((0, 0, 255))  # Blue
            else:
                window.fill((0, 0, 0))  # Black

    def stop(self) -> None:
        """Stop recording and save the click track."""
        logger.info(f"stop() called, {len(self._recorded_audio)} audio blocks recorded")

        # Remove from cleanup list
        if self in _active_instances:
            _active_instances.remove(self)

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Error stopping stream: {e}")
            self._stream = None

        # Save click track (only once)
        if self._recorded_audio:
            self._save_click_track()
            self._recorded_audio = []  # Prevent double-save
        else:
            logger.warning("No audio recorded!")

    def _save_click_track(self) -> None:
        """Generate and save a WAV with beeps at onset times."""
        if not self._recorded_audio:
            logger.warning("_save_click_track called with no audio")
            return

        try:
            import scipy.io.wavfile as wav

            # Calculate total duration from recorded audio
            total_samples = sum(len(block) for block in self._recorded_audio)
            total_duration = total_samples / self.SAMPLERATE

            print(
                f"\n*** Saving {len(self._onset_times)} beeps to {self._output_file} ***\n"
            )
            logger.info(
                f"Saving {total_duration:.1f}s with {len(self._onset_times)} beeps"
            )

            # Generate click track (just beeps, no original audio)
            clicks = np.zeros(total_samples, dtype=np.float32)

            # Create beep sounds: low for main beat, high for other
            click_duration = 0.01
            click_samples = int(click_duration * self.SAMPLERATE)
            t = np.arange(click_samples) / self.SAMPLERATE
            main_beat_sound = np.sin(2 * np.pi * 500 * t) * 0.8  # 500Hz low beep
            other_beat_sound = np.sin(2 * np.pi * 2000 * t) * 0.8  # 2000Hz high beep

            # Place beeps at onset times
            placed_main = 0
            placed_other = 0
            for i, onset_time in enumerate(self._onset_times):
                sample_idx = int(onset_time * self.SAMPLERATE)
                is_main = (
                    self._onset_is_main_beat[i]
                    if i < len(self._onset_is_main_beat)
                    else False
                )
                sound = main_beat_sound if is_main else other_beat_sound
                label = "MAIN" if is_main else "other"
                print(
                    f"  [{label}] onset_time={onset_time:.3f}s -> sample_idx={sample_idx}"
                )
                if 0 <= sample_idx < len(clicks) - len(sound):
                    clicks[sample_idx : sample_idx + len(sound)] = sound
                    if is_main:
                        placed_main += 1
                    else:
                        placed_other += 1
            print(
                f"  Placed {placed_main} main + {placed_other} other = {placed_main + placed_other} beeps"
            )

            # Convert to int16
            clicks_int16 = (clicks * 32767).astype(np.int16)

            wav.write(self._output_file, self.SAMPLERATE, clicks_int16)
            print(f"*** SAVED: {self._output_file} ***")
            logger.info(f"Saved beep track to: {self._output_file}")

        except Exception as e:
            print(f"*** FAILED TO SAVE: {e} ***")
            logger.warning(f"Failed to save click track: {e}")

    def __del__(self) -> None:
        """Cleanup on destruction."""
        if hasattr(self, "_stream"):
            self.stop()
