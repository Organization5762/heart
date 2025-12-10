"""Shared beat state for syncing animations across renderers.

The BeatFlashRenderer updates this state, and other renderers can read from it
to sync their animations to the detected beat.
"""

import time as _time
from dataclasses import dataclass, field


@dataclass
class BeatState:
    """Current beat detection state."""

    # Beat timing
    interval: float | None = None  # Seconds between beats (e.g., 0.5s for 120 BPM)
    phase: float = 0.0  # Wall time of last confirmed beat

    # Monotonic beat counter - never resets, only increments
    beat_count: int = 0
    _last_phase_beat: int = field(default=-1, repr=False)

    # Recording timing for conversion
    recording_start_wall_time: float = 0.0

    def get_beat_phase(self) -> float:
        """Get current phase within the beat cycle (0.0 to 1.0).

        Returns 0.0 if no beat detected yet.
        """
        if self.interval is None or self.interval <= 0:
            return 0.0

        now = _time.time()
        time_since_phase = now - self.phase
        return (time_since_phase / self.interval) % 1.0

    def get_bpm(self) -> float | None:
        """Get current BPM, or None if no beat detected."""
        if self.interval is None or self.interval <= 0:
            return None
        return 60.0 / self.interval

    def is_on_beat(self, window: float = 0.1) -> bool:
        """Check if we're currently on a beat.

        Args:
            window: Phase window around beat (0.1 = 10% of beat)

        Returns:
            True if phase is within window of beat
        """
        if self.interval is None:
            return False
        phase = self.get_beat_phase()
        return phase < window or phase > (1.0 - window)

    def get_beat_number(self) -> int:
        """Get monotonically increasing beat number.

        This counts total beats since detection started, never resets.
        """
        if self.interval is None or self.interval <= 0:
            return self.beat_count

        # Calculate how many beats since last phase update
        now = _time.time()
        time_since_phase = now - self.phase
        beats_since_phase = int(time_since_phase / self.interval)

        return self.beat_count + beats_since_phase


# Global shared beat state - updated by BeatFlashRenderer
_beat_state = BeatState()


def get_beat_state() -> BeatState:
    """Get the shared beat state."""
    return _beat_state


def update_beat_state(
    interval: float | None = None,
    phase: float | None = None,
    recording_start_wall_time: float | None = None,
    clear_interval: bool = False,
) -> None:
    """Update the shared beat state."""
    global _beat_state

    # Clear interval if requested (beat lost)
    if clear_interval:
        _beat_state.interval = None
    # Set interval if provided
    elif interval is not None:
        _beat_state.interval = interval

    # When phase is updated with an existing interval, lock in beat count
    if phase is not None:
        if _beat_state.interval is not None and _beat_state.phase > 0:
            # Calculate beats elapsed between old and new phase
            # Use new phase time (not current time) to accurately count beats
            time_between_phases = phase - _beat_state.phase
            if time_between_phases > 0:
                beats_between = int(round(time_between_phases / _beat_state.interval))
                _beat_state.beat_count += beats_between
        _beat_state.phase = phase

    if recording_start_wall_time is not None:
        _beat_state.recording_start_wall_time = recording_start_wall_time
