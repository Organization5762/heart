from heart.events.types import PhoneTextMessage
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.phone_text import PhoneText


class TestPeripheralPhoneTextEventBus:
    """Group Peripheral Phone Text Event Bus tests so peripheral phone text event bus behaviour stays reliable. This preserves confidence in peripheral phone text event bus for end-to-end scenarios."""

    def test_phone_text_emits_message_event(self):
        """Verify that phone text emits message event. This ensures event orchestration remains reliable."""
        bus = EventBus()
        captured: list[str] = []

        bus.subscribe(
            PhoneTextMessage.EVENT_TYPE, lambda event: captured.append(event.data["text"])
        )

        phone = PhoneText(event_bus=bus, producer_id=3)

        phone._on_write(b"hello world\0", None)

        assert captured == ["hello world"]
        assert phone.pop_text() == "hello world"
