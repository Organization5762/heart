from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from PIL import Image

from heart.events.types import DisplayFrame
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.led_matrix import LEDMatrixDisplay


def _solid_image(width: int, height: int, *, value: int) -> Image.Image:
    array = np.full((height, width, 3), value, dtype=np.uint8)
    return Image.fromarray(array, mode="RGB")


def test_publish_image_emits_event_and_updates_state_store() -> None:
    bus = EventBus()
    peripheral = LEDMatrixDisplay(width=4, height=2, event_bus=bus)

    image = _solid_image(4, 2, value=128)
    peripheral.publish_image(
        image, timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )

    latest = peripheral.latest_frame
    assert latest is not None
    assert latest.frame_id == 0
    assert latest.width == 4 and latest.height == 2
    assert latest.mode == "RGB"
    assert latest.data == image.tobytes()
    reconstructed = latest.to_image()
    assert reconstructed.tobytes() == image.tobytes()

    state_entry = bus.state_store.get_latest(DisplayFrame.EVENT_TYPE)
    assert state_entry is not None
    assert isinstance(state_entry.data, DisplayFrame)
    assert state_entry.data.data == image.tobytes()


def test_publish_image_increments_frame_id(monkeypatch) -> None:
    bus = EventBus()
    peripheral = LEDMatrixDisplay(width=2, height=2, event_bus=bus)
    image = _solid_image(2, 2, value=64)

    first = peripheral.publish_image(image)
    second = peripheral.publish_image(image)

    assert first.frame_id == 0
    assert second.frame_id == 1
    assert bus.state_store.get_latest(DisplayFrame.EVENT_TYPE).data.frame_id == 1


def test_publish_image_validates_dimensions() -> None:
    peripheral = LEDMatrixDisplay(width=2, height=2)
    image = _solid_image(3, 2, value=10)

    try:
        peripheral.publish_image(image)
    except ValueError as exc:
        assert "dimensions" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("ValueError expected when dimensions do not match")
