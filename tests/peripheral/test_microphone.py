import numpy as np
import pytest

from heart.peripheral import microphone
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.microphone import Microphone


class TestPeripheralMicrophone:
    """Group Peripheral Microphone tests so peripheral microphone behaviour stays reliable. This preserves confidence in peripheral microphone for end-to-end scenarios."""

    def test_detect_without_sounddevice(self, monkeypatch):
        """Detection should short-circuit when sounddevice is unavailable."""

        monkeypatch.setattr(microphone, "sd", None)
        assert list(Microphone.detect()) == []



    def test_process_audio_chunk_emits_event(self):
        """Processing an audio block stores metrics and emits an event."""

        bus = EventBus()
        captured: list[dict] = []

        def _capture(event):
            captured.append(event.data)

        bus.subscribe(Microphone.EVENT_LEVEL, _capture)

        mic = Microphone(event_bus=bus)
        audio = np.array([[0.0], [0.5], [-0.5], [0.0]], dtype=np.float32)

        mic._process_audio_chunk(audio, frames=audio.shape[0])

        level = mic.latest_level
        assert level is not None
        assert level["frames"] == audio.shape[0]
        assert level["samplerate"] == mic.samplerate
        assert level["peak"] == pytest.approx(0.5)
        assert level["rms"] == pytest.approx(np.sqrt(0.125))

        assert captured
        assert captured[0] == level
