#!/usr/bin/env python3
"""Standalone beat detection debug UI.

Visualizes audio waveform, spectral flux, and detected onsets in real-time.

Usage:
    uv run python scripts/beat_debug_ui.py
    uv run python scripts/beat_debug_ui.py --device loopback
"""

import argparse
import sys
import threading
from typing import Any

import numpy as np
import pygame

# Import audio processor
sys.path.insert(0, "src")
from heart.display.audio_processor import AudioProcessor

# Try to import sounddevice
try:
    import sounddevice as sd
except ImportError:
    print("Error: sounddevice not installed. Run: uv add sounddevice")
    sys.exit(1)


class BeatDebugUI:
    """Real-time beat detection visualization."""

    # Window settings
    WIDTH = 1400
    HEIGHT = 800
    FPS = 60

    # Timeline settings
    VISIBLE_SECONDS = 10.0  # How many seconds visible at once
    PIXELS_PER_SECOND = 100  # Zoom level

    # Colors
    BG_COLOR = (20, 20, 25)
    GRID_COLOR = (40, 40, 50)
    TEXT_COLOR = (200, 200, 200)
    WAVEFORM_COLOR = (80, 180, 80)
    FLUX_COLOR = (80, 80, 200)
    THRESHOLD_COLOR = (200, 80, 80)
    ONSET_COLOR = (255, 100, 100)
    MAIN_BEAT_COLOR = (100, 255, 100)
    BEAT_GRID_COLOR = (60, 100, 60)
    REJECTED_COLOR = (255, 165, 0)  # Orange for rejected onsets

    def __init__(self, device: int | str | None = None, sensitivity: float = 1.0):
        """Initialize the debug UI.

        Args:
            device: Audio input device (None for default, 'loopback' to auto-detect)
            sensitivity: Beat detection sensitivity
        """
        self._device = device
        self._processor = AudioProcessor(sensitivity=sensitivity)
        self._stream: Any = None
        self._running = False
        self._lock = threading.Lock()

        # Scroll position (in seconds)
        self._scroll_offset = 0.0
        self._auto_scroll = True  # Follow current time

        # Initialize pygame
        pygame.init()
        self._screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Beat Detection Debug")
        self._clock = pygame.time.Clock()
        self._font = pygame.font.Font(None, 24)
        self._small_font = pygame.font.Font(None, 18)

    def _find_loopback_device(self) -> int | None:
        """Find a loopback/system audio device."""
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            name = d["name"].lower()
            if d["max_input_channels"] > 0 and (
                "loopback" in name
                or "blackhole" in name
                or "soundflower" in name
                or "what u hear" in name
                or "stereo mix" in name
            ):
                print(f"Found loopback device: {d['name']}")
                return i
        return None

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info: Any, status: Any
    ) -> None:
        """Process incoming audio."""
        if status:
            print(f"Audio status: {status}")

        audio = indata[:, 0].astype(np.float32)
        stream_time = time_info.inputBufferAdcTime

        with self._lock:
            onset = self._processor.process_block(audio, stream_time)
            if onset:
                bpm = self._processor.bpm
                if onset.is_main:
                    print(f"MAIN | {bpm:.0f} BPM" if bpm else "MAIN")
                else:
                    print("onset")

    def _start_audio(self) -> bool:
        """Start audio capture."""
        device = self._device

        # Auto-detect loopback
        if device == "loopback":
            device = self._find_loopback_device()
            if device is None:
                print("No loopback device found. Available devices:")
                print(sd.query_devices())
                return False

        try:
            self._stream = sd.InputStream(
                device=device,
                channels=1,
                samplerate=AudioProcessor.SAMPLERATE,
                blocksize=AudioProcessor.BLOCK_SIZE,
                callback=self._audio_callback,
            )
            self._stream.start()
            print(f"Started audio capture (device={device})")
            return True
        except Exception as e:
            print(f"Failed to start audio: {e}")
            print("Available devices:")
            print(sd.query_devices())
            return False

    def _stop_audio(self) -> None:
        """Stop audio capture."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _time_to_x(self, t: float) -> int:
        """Convert audio time to screen x coordinate."""
        return int((t - self._scroll_offset) * self.PIXELS_PER_SECOND) + 100

    def _x_to_time(self, x: int) -> float:
        """Convert screen x to audio time."""
        return (x - 100) / self.PIXELS_PER_SECOND + self._scroll_offset

    def _draw_grid(self, y_start: int, height: int, label: str) -> None:
        """Draw time grid for a timeline section."""
        # Background
        pygame.draw.rect(self._screen, (30, 30, 35), (0, y_start, self.WIDTH, height))

        # Label
        label_surf = self._font.render(label, True, self.TEXT_COLOR)
        self._screen.blit(label_surf, (10, y_start + 5))

        # Vertical grid lines (every second)
        start_sec = int(self._scroll_offset)
        end_sec = int(self._scroll_offset + self.VISIBLE_SECONDS) + 2

        for sec in range(start_sec, end_sec):
            x = self._time_to_x(sec)
            if 100 <= x <= self.WIDTH - 50:
                # Major line every second
                pygame.draw.line(
                    self._screen, self.GRID_COLOR, (x, y_start), (x, y_start + height)
                )
                # Time label
                time_str = f"{sec}s"
                time_surf = self._small_font.render(time_str, True, (100, 100, 100))
                self._screen.blit(time_surf, (x - 10, y_start + height - 15))

        # Beat grid if we have a beat
        with self._lock:
            beat = self._processor.state.beat
            if beat.interval and beat.phase:
                # Draw expected beat times
                t = beat.phase
                while t > self._scroll_offset:
                    t -= beat.interval
                while t < self._scroll_offset + self.VISIBLE_SECONDS + 1:
                    x = self._time_to_x(t)
                    if 100 <= x <= self.WIDTH - 50:
                        pygame.draw.line(
                            self._screen,
                            self.BEAT_GRID_COLOR,
                            (x, y_start),
                            (x, y_start + height),
                        )
                    t += beat.interval

    def _intensity_to_color(self, intensity: float) -> tuple[int, int, int]:
        """Convert intensity (0-1) to a viridis-like color."""
        # Simple viridis-like colormap: dark purple -> blue -> green -> yellow
        if intensity < 0.25:
            t = intensity / 0.25
            r = int(30 + t * 30)
            g = int(0 + t * 30)
            b = int(80 + t * 40)
        elif intensity < 0.5:
            t = (intensity - 0.25) / 0.25
            r = int(60 - t * 30)
            g = int(30 + t * 80)
            b = int(120 + t * 30)
        elif intensity < 0.75:
            t = (intensity - 0.5) / 0.25
            r = int(30 + t * 150)
            g = int(110 + t * 80)
            b = int(150 - t * 100)
        else:
            t = (intensity - 0.75) / 0.25
            r = int(180 + t * 75)
            g = int(190 + t * 65)
            b = int(50 - t * 50)
        return (min(255, max(0, r)), min(255, max(0, g)), min(255, max(0, b)))

    def _draw_spectrogram(self, y_start: int, height: int) -> None:
        """Draw spectrogram timeline."""
        self._draw_grid(y_start, height, "Spectrogram (0-500 Hz)")

        with self._lock:
            spectrums = self._processor.state.spectrums
            times = self._processor.state.block_times

            if not spectrums or len(spectrums) < 2:
                return

            # Find max for normalization (use log scale)
            all_max = 0.0
            for spec in spectrums:
                if len(spec) > 0:
                    all_max = max(all_max, np.max(spec))
            if all_max == 0:
                all_max = 1.0

            # Focus on bass frequencies (0-500 Hz) - about 25 bins at 44100/1024
            # Each bin is ~43 Hz
            max_freq_bin = 12  # ~500 Hz
            usable_height = height - 30  # Leave room for label
            bin_height = usable_height // max_freq_bin  # Height per frequency bin

            # Calculate time per block for width
            block_duration = AudioProcessor.BLOCK_SIZE / AudioProcessor.SAMPLERATE
            pixels_per_block = max(2, int(block_duration * self.PIXELS_PER_SECOND))

            for i, (spec, t) in enumerate(zip(spectrums, times)):
                x_start = self._time_to_x(t)
                x_end = x_start + pixels_per_block

                if x_end < 100 or x_start > self.WIDTH - 50:
                    continue

                # Draw column of spectrum (each bin as a rectangle)
                for bin_idx in range(min(max_freq_bin, len(spec))):
                    # Map bin to y position (low freq at bottom, high at top)
                    y = y_start + usable_height - (bin_idx + 1) * bin_height

                    # Log scale for intensity
                    val = spec[bin_idx]
                    if val > 0:
                        log_val = np.log10(val + 1) / np.log10(all_max + 1)
                    else:
                        log_val = 0

                    color = self._intensity_to_color(log_val)
                    pygame.draw.rect(
                        self._screen,
                        color,
                        (max(100, x_start), y, pixels_per_block, bin_height),
                    )

    def _draw_flux(self, y_start: int, height: int) -> None:
        """Draw spectral flux timeline."""
        self._draw_grid(y_start, height, "Flux / Threshold")

        with self._lock:
            flux_vals = self._processor.state.flux_values
            thresholds = self._processor.state.thresholds
            times = self._processor.state.block_times

            if not flux_vals:
                return

            # Find max for scaling
            max_flux = max(flux_vals) if flux_vals else 1
            if max_flux == 0:
                max_flux = 1
            scale = (height - 40) / max_flux

            bottom_y = y_start + height - 20

            # Draw flux
            prev_x, prev_y = None, None
            for i, (flux, t) in enumerate(zip(flux_vals, times)):
                x = self._time_to_x(t)
                if 100 <= x <= self.WIDTH - 50:
                    y = bottom_y - int(flux * scale)
                    if prev_x is not None:
                        pygame.draw.line(
                            self._screen, self.FLUX_COLOR, (prev_x, prev_y), (x, y)
                        )
                    prev_x, prev_y = x, y
                else:
                    prev_x, prev_y = None, None

            # Draw threshold
            prev_x, prev_y = None, None
            for i, (thresh, t) in enumerate(zip(thresholds, times)):
                x = self._time_to_x(t)
                if 100 <= x <= self.WIDTH - 50:
                    y = bottom_y - int(thresh * scale)
                    if prev_x is not None:
                        pygame.draw.line(
                            self._screen,
                            self.THRESHOLD_COLOR,
                            (prev_x, prev_y),
                            (x, y),
                        )
                    prev_x, prev_y = x, y
                else:
                    prev_x, prev_y = None, None

    def _draw_onsets(self, y_start: int, height: int) -> None:
        """Draw onset markers timeline."""
        self._draw_grid(y_start, height, "Onsets (orange=rejected)")

        with self._lock:
            onsets = self._processor.state.onsets
            rejected = self._processor.state.rejected_onsets

            center_y = y_start + height // 2

            # Draw rejected onsets first (so accepted ones draw on top)
            for rej in rejected:
                x = self._time_to_x(rej.time)
                if 100 <= x <= self.WIDTH - 50:
                    # Dashed vertical line for rejected
                    for dy in range(20, height - 20, 8):
                        pygame.draw.line(
                            self._screen,
                            self.REJECTED_COLOR,
                            (x, y_start + dy),
                            (x, y_start + dy + 4),
                            1,
                        )

                    # Icon based on rejection type
                    # M = too much mid (low/mid ratio failed)
                    # H = too much high (high/low ratio failed)
                    if "low/mid" in rej.reason:
                        # Draw "M" - too much mid frequency
                        icon = "M"
                        icon_y = center_y - 6
                    else:
                        # Draw "H" - too much high frequency
                        icon = "H"
                        icon_y = center_y - 6

                    icon_surf = self._small_font.render(icon, True, self.REJECTED_COLOR)
                    self._screen.blit(icon_surf, (x - 4, icon_y))

            # Draw accepted onsets
            for onset in onsets:
                x = self._time_to_x(onset.time)
                if 100 <= x <= self.WIDTH - 50:
                    color = self.MAIN_BEAT_COLOR if onset.is_main else self.ONSET_COLOR
                    width = 4 if onset.is_main else 2

                    # Vertical line
                    pygame.draw.line(
                        self._screen,
                        color,
                        (x, y_start + 20),
                        (x, y_start + height - 20),
                        width,
                    )

                    # Circle at center
                    radius = 8 if onset.is_main else 4
                    pygame.draw.circle(self._screen, color, (x, center_y), radius)

    def _draw_status(self) -> None:
        """Draw status bar at top."""
        with self._lock:
            current_time = self._processor.current_time
            bpm = self._processor.bpm
            beat = self._processor.state.beat
            num_onsets = len(self._processor.state.onsets)

        # Background
        pygame.draw.rect(self._screen, (40, 40, 45), (0, 0, self.WIDTH, 40))

        # Status text
        status_parts = [
            f"Time: {current_time:.1f}s",
            f"Onsets: {num_onsets}",
        ]
        if bpm:
            status_parts.append(f"BPM: {bpm:.0f}")
            status_parts.append("LOCKED" if beat.is_locked else "tracking")
        else:
            status_parts.append("Searching...")

        status_text = " | ".join(status_parts)
        text_surf = self._font.render(status_text, True, self.TEXT_COLOR)
        self._screen.blit(text_surf, (10, 10))

        # Controls hint
        hint = "Scroll: ← → or touchpad | Space: Auto-scroll | R: Reset | Q: Quit"
        hint_surf = self._small_font.render(hint, True, (100, 100, 100))
        self._screen.blit(hint_surf, (self.WIDTH - hint_surf.get_width() - 10, 15))

    def _handle_events(self) -> bool:
        """Handle pygame events. Returns False to quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_SPACE:
                    self._auto_scroll = not self._auto_scroll
                elif event.key == pygame.K_r:
                    with self._lock:
                        self._processor.reset()
                    self._scroll_offset = 0
                elif event.key == pygame.K_LEFT:
                    self._auto_scroll = False
                    self._scroll_offset = max(0, self._scroll_offset - 1)
                elif event.key == pygame.K_RIGHT:
                    self._auto_scroll = False
                    self._scroll_offset += 1
            elif event.type == pygame.MOUSEWHEEL:
                self._auto_scroll = False
                # Horizontal scroll (touchpad two-finger swipe)
                if event.x != 0:
                    self._scroll_offset -= event.x * 0.3
                # Vertical scroll (also works for horizontal timeline)
                if event.y != 0:
                    self._scroll_offset -= event.y * 0.5
                self._scroll_offset = max(0, self._scroll_offset)

        return True

    def run(self) -> None:
        """Run the debug UI main loop."""
        if not self._start_audio():
            return

        self._running = True

        try:
            while self._running:
                # Handle events
                if not self._handle_events():
                    break

                # Auto-scroll to follow current time
                if self._auto_scroll:
                    with self._lock:
                        current = self._processor.current_time
                    # Keep current time at 80% of visible area
                    target = current - self.VISIBLE_SECONDS * 0.8
                    self._scroll_offset = max(0, target)

                # Clear screen
                self._screen.fill(self.BG_COLOR)

                # Draw timelines
                section_height = (self.HEIGHT - 40) // 3

                self._draw_status()
                self._draw_spectrogram(40, section_height)
                self._draw_onsets(40 + section_height, section_height)
                self._draw_flux(40 + section_height * 2, section_height)

                # Update display
                pygame.display.flip()
                self._clock.tick(self.FPS)

        finally:
            self._stop_audio()
            pygame.quit()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Beat detection debug UI")
    parser.add_argument(
        "--device",
        "-d",
        default="loopback",
        help="Audio device (default: loopback). Use integer for specific device.",
    )
    parser.add_argument(
        "--sensitivity",
        "-s",
        type=float,
        default=1.0,
        help="Beat detection sensitivity (default: 1.0)",
    )
    parser.add_argument(
        "--list-devices",
        "-l",
        action="store_true",
        help="List available audio devices and exit",
    )

    args = parser.parse_args()

    if args.list_devices:
        print("Available audio devices:")
        print(sd.query_devices())
        return

    # Parse device
    device: int | str | None = args.device
    if device and device.isdigit():
        device = int(device)

    ui = BeatDebugUI(device=device, sensitivity=args.sensitivity)
    ui.run()


if __name__ == "__main__":
    main()
