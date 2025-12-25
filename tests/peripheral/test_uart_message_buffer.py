"""Tests for BLE UART buffering behavior."""

from __future__ import annotations

from heart.peripheral.uart_buffer import UartMessageBuffer
from heart.utilities.env import BleUartBufferStrategy


class TestUartMessageBuffer:
    """Cover UART buffering modes so streaming IO remains reliable under load."""

    def test_bytes_strategy_reassembles_split_payloads(self) -> None:
        """Ensure byte buffering stitches split frames to preserve event integrity in BLE streams."""

        buffer = UartMessageBuffer(
            strategy_provider=lambda: BleUartBufferStrategy.BYTES
        )

        messages = list(buffer.append(b'{"alpha": 1}\n{"beta": '))
        assert messages == [b'{"alpha": 1}']
        assert buffer.buffer_size == len(b'{"beta": ')

        messages = list(buffer.append(b'2}\n'))
        assert messages == [b'{"beta": 2}']
        assert buffer.buffer_size == 0

    def test_text_strategy_returns_decoded_lines(self) -> None:
        """Ensure text buffering preserves line boundaries for compatibility with legacy parsing."""

        buffer = UartMessageBuffer(strategy_provider=lambda: BleUartBufferStrategy.TEXT)

        messages = list(buffer.append(b'{"ok": true}\n{"pending":'))
        assert messages == ['{"ok": true}']
        assert buffer.buffer_size == len('{"pending":')

        messages = list(buffer.append(b' false}\n'))
        assert messages == ['{"pending": false}']
        assert buffer.buffer_size == 0
