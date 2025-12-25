
from heart.peripheral import microphone
from heart.peripheral.microphone import Microphone


class TestPeripheralMicrophone:
    """Group Peripheral Microphone tests so peripheral microphone behaviour stays reliable. This preserves confidence in peripheral microphone for end-to-end scenarios."""

    def test_detect_without_sounddevice(self, monkeypatch):
        """Verify detect short-circuits without sounddevice so deployments degrade gracefully."""

        monkeypatch.setattr(microphone, "sd", None)
        assert list(Microphone.detect()) == []
