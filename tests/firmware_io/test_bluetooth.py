
import pytest
from helpers.firmware_io import StubBLE, StubUART

from heart.firmware_io import bluetooth


@pytest.mark.parametrize(
    "connected, advertising, message, expected_starts, expected_writes",
    [
        (True, False, "ping", 1, [b"ping", bluetooth.END_OF_MESSAGE_DELIMETER.encode(bluetooth.ENCODING)]),
        (True, True, "pong", 0, [b"pong", bluetooth.END_OF_MESSAGE_DELIMETER.encode(bluetooth.ENCODING)]),
        (False, False, "idle", 1, []),
    ],
)
def test_send_handles_advertising_and_buffer_flush(
    monkeypatch, connected, advertising, message, expected_starts, expected_writes
) -> None:
    stub_ble = StubBLE(advertising=advertising, connected=connected)
    stub_uart = StubUART()
    advertisement = object()

    monkeypatch.setattr(bluetooth, "ble", stub_ble)
    monkeypatch.setattr(bluetooth, "uart", stub_uart)
    monkeypatch.setattr(bluetooth, "advertisement", advertisement)

    bluetooth.send([message])

    assert len(stub_ble.started_advertising_with) == expected_starts
    if expected_starts:
        assert stub_ble.started_advertising_with[0] is advertisement

    if expected_writes:
        assert stub_uart.written == expected_writes
    else:
        assert stub_uart.written == []


def test_send_encodes_multiple_messages(monkeypatch) -> None:
    stub_ble = StubBLE(advertising=True, connected=True)
    stub_uart = StubUART()

    monkeypatch.setattr(bluetooth, "ble", stub_ble)
    monkeypatch.setattr(bluetooth, "uart", stub_uart)

    bluetooth.send(["one", "two"])

    expected = [
        b"one",
        bluetooth.END_OF_MESSAGE_DELIMETER.encode(bluetooth.ENCODING),
        b"two",
        bluetooth.END_OF_MESSAGE_DELIMETER.encode(bluetooth.ENCODING),
    ]
    assert stub_uart.written == expected