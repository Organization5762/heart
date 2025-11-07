from heart.events.types import PhoneTextMessage
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.phone_text import PhoneText


def test_phone_text_emits_message_event():
    bus = EventBus()
    captured: list[str] = []

    bus.subscribe(
        PhoneTextMessage.EVENT_TYPE, lambda event: captured.append(event.data["text"])
    )

    phone = PhoneText(event_bus=bus, producer_id=3)

    phone._on_write(b"hello world\0", None)

    assert captured == ["hello world"]
    assert phone.pop_text() == "hello world"
